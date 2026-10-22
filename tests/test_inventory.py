import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from inventory_review import build_review, load_inputs, DATA_DIR
from scripts.generate_demo import generate


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = load_inputs()
        cls.report = build_review(cls.inputs)
        cls.items = {row['sku']:row for row in cls.report['items']}

    def test_independent_expected_decisions(self):
        expected=json.loads((Path(__file__).parent/'fixtures'/'inventory_expected.json').read_text())
        for sku, values in expected.items():
            for field, value in values.items():
                with self.subTest(sku=sku,field=field):
                    self.assertEqual(self.items[sku][field], value)

    def test_data_scale_period_and_reproducibility(self):
        self.assertEqual(len(self.inputs['products']),20)
        self.assertEqual(len(self.inputs['sales']),3661)
        self.assertEqual(self.inputs['metadata']['history_start'],'2026-04-01')
        with tempfile.TemporaryDirectory() as root:
            first,second=Path(root)/'first',Path(root)/'second'
            generate(first,Path(root)/'key1')
            generate(second,Path(root)/'key2')
            self.assertEqual({p.name:p.read_bytes() for p in first.iterdir()}, {p.name:p.read_bytes() for p in second.iterdir()})
            self.assertEqual((first/'sales.json').read_bytes(), (DATA_DIR/'sales.json').read_bytes())

    def test_reservations_and_returns_are_not_silently_netted(self):
        item=self.items['SKU-001']
        self.assertEqual(item['available'],40)
        self.assertEqual(item['window_sales'],300)
        self.assertEqual(item['window_returns'],2)
        self.assertEqual(item['first_shortage_date'],'2026-10-05')

    def test_partial_and_cancelled_orders_are_not_available_stock(self):
        self.assertEqual(self.items['SKU-003']['overdue_quantity'],60)
        self.assertEqual(self.items['SKU-003']['available'],12)
        self.assertEqual(self.items['SKU-003']['confirmed_incoming'],0)
        self.assertEqual(self.items['SKU-009']['confirmed_incoming'],0)
        self.assertEqual(self.items['SKU-002']['suggested_quantity'],0)

    def test_late_incoming_does_not_trigger_duplicate_full_order(self):
        inputs=copy.deepcopy(self.inputs)
        inputs['incoming_orders'][0]['due_date']='2026-10-09'
        item=next(i for i in build_review(inputs)['items'] if i['sku']=='SKU-002')
        self.assertEqual(item['status'],'EXPEDITE_EXISTING')
        self.assertEqual(item['suggested_quantity'],0)
        self.assertEqual(item['first_shortage_date'],'2026-10-05')

    def test_partial_receipt_counts_only_the_outstanding_units(self):
        inputs=copy.deepcopy(self.inputs)
        inputs['incoming_orders'][1]['due_date']='2026-10-03'
        item=next(i for i in build_review(inputs)['items'] if i['sku']=='SKU-003')
        self.assertEqual(item['confirmed_incoming'],60)
        self.assertEqual(item['stock_position'],72)
        self.assertEqual(item['status'],'INCOMING_COVERED')
        self.assertEqual(item['suggested_quantity'],0)

    def test_quote_constraints_and_lowest_total_cost(self):
        rows={q['quote_id']:q for i in self.items.values() for q in i['quotations']}
        self.assertEqual(self.items['SKU-008']['selected_quote_id'],'Q-008-B')
        self.assertEqual(rows['Q-008-A']['economics']['landed_cost'],7)
        self.assertEqual(rows['Q-008-B']['economics']['landed_cost'],4)
        self.assertEqual(rows['Q-005-A']['order_quantity'],500)
        self.assertFalse(rows['Q-005-A']['eligible'])
        self.assertIn('budget',' '.join(rows['Q-005-A']['issues']))
        for quote_id in ('Q-006-A','Q-007-A','Q-001-C'):
            self.assertIsNone(rows[quote_id]['economics'])
            self.assertFalse(rows[quote_id]['eligible'])
        self.assertIn('expired',' '.join(rows['Q-001-D']['issues']))
        self.assertFalse(rows['Q-009-A']['eligible'])
        self.assertEqual(self.items['SKU-009']['selected_quote_id'],'Q-009-B')

    def test_reorder_at_boundary_and_rounding(self):
        inputs=copy.deepcopy(self.inputs)
        inputs['inventory'][0]['on_hand']=220
        item=next(i for i in build_review(inputs)['items'] if i['sku']=='SKU-001')
        self.assertEqual(item['stock_position'],210)
        self.assertEqual(item['suggested_quantity'],140)

    def test_bad_inputs_fail_instead_of_showing_healthy_stock(self):
        cases=[]
        bad=copy.deepcopy(self.inputs);bad['inventory'][0]['reserved']=51;cases.append(bad)
        bad=copy.deepcopy(self.inputs);bad['products'].append(bad['products'][0]);cases.append(bad)
        bad=copy.deepcopy(self.inputs);bad['sales']=[r for r in bad['sales'] if not(r['sku']=='SKU-001' and r['date']=='2026-09-30')];cases.append(bad)
        bad=copy.deepcopy(self.inputs);bad['quotations'][0]['shipping_per_unit']='NaN';cases.append(bad)
        bad=copy.deepcopy(self.inputs);bad['incoming_orders'][0]['received']=201;cases.append(bad)
        for inputs in cases:
            with self.subTest(case=cases.index(inputs)),self.assertRaises(ValueError):build_review(inputs)

    def test_application_loader_cannot_see_answer_key(self):
        paths=[]
        original=Path.read_text
        def tracked(path,*args,**kwargs):
            paths.append(path)
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',tracked):load_inputs()
        self.assertEqual(len(paths),6)
        self.assertTrue(all(path.parent==DATA_DIR for path in paths))
        self.assertNotIn('inventory_expected.json',[p.name for p in paths])
        self.assertEqual(self.report['mode'],'synthetic-rules-only')
        self.assertFalse(self.items['SKU-001']['handoff']['email_sending_enabled'])


if __name__=='__main__':unittest.main()
