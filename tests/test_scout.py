import csv
import io
import math
import unittest
from dataclasses import replace
from market_scout import calculate_margin, sample_record, artifacts
from scout_agent import run_investigation, Investigator, DemoResearch


class EconomicsTests(unittest.TestCase):
    def setUp(self):
        self.record = replace(sample_record('gloves'), wholesale_price=40, retail_benchmark=120, shipping_per_unit=5, duty_per_unit=5, moq=10)

    def test_vat_costs_and_whole_unit_breakeven(self):
        result = calculate_margin(self.record, .2, .5, 501)
        self.assertEqual(result['net_retail_price'], 100)
        self.assertEqual(result['vat_amount'], 20)
        self.assertEqual(result['landed_cost'], 50)
        self.assertEqual(result['gross_profit'], 50)
        self.assertEqual(result['gross_margin_percent'], 50)
        self.assertEqual(result['breakeven_units'], 11)
        self.assertEqual(result['moq_cost'], 500)
        self.assertEqual(result['decision'], 'GO')

    def test_missing_shipping_is_not_zero(self):
        result = calculate_margin(replace(self.record, shipping_per_unit=None))
        self.assertEqual(result['decision'], 'INCOMPLETE')
        self.assertIsNone(result['gross_margin'])
        self.assertIn('shipping_per_unit', result['missing_fields'])

    def test_margin_decision_uses_unrounded_values(self):
        record=replace(self.record, wholesale_price=50.0001, shipping_per_unit=0, duty_per_unit=0)
        self.assertEqual(calculate_margin(record,.2,.5)['decision'],'NO-GO')

    def test_loss_and_zero_profit_have_no_finite_breakeven(self):
        for price in (100,101):
            result=calculate_margin(replace(self.record,wholesale_price=price,shipping_per_unit=0,duty_per_unit=0))
            self.assertIsNone(result['breakeven_units'])
            self.assertEqual(result['decision'],'NO-GO')

    def test_bad_numbers_and_rates(self):
        for value in (float('nan'),float('inf'),-1,True,'20'):
            with self.subTest(value=value),self.assertRaises(ValueError):
                calculate_margin(self.record,vat_rate=value)
        with self.assertRaises(ValueError): calculate_margin(self.record,target_margin=1.1)
        with self.assertRaises(ValueError): calculate_margin(replace(self.record, moq=True))

    def test_csv_currency_and_formula_escape(self):
        result=calculate_margin(replace(self.record,currency='USD',product_title='=EVIL()'))
        row=list(csv.DictReader(io.StringIO(artifacts(result)['catalog_entry.csv'])))[0]
        self.assertEqual(row['currency'],'USD')
        self.assertEqual(row['sku_name'],"'=EVIL()")
        self.assertNotIn('est_wholesale_eur',row)
        self.assertIn('DRAFT ONLY',artifacts(result)['supplier_rfq.txt'])

    def test_unknown_export_does_not_crash(self):
        result=calculate_margin(replace(self.record,retail_benchmark=None))
        self.assertIn('INCOMPLETE',artifacts(result)['catalog_entry.csv'])


class AgentTests(unittest.TestCase):
    def test_demo_executes_tools_and_resolves_missing_cost(self):
        run=run_investigation('gloves',demo=True)
        self.assertEqual(run['mode'],'offline-demo')
        self.assertEqual(run['research_calls'],2)
        self.assertEqual(run['trace'][1]['result']['decision'],'INCOMPLETE')
        self.assertEqual(run['result']['landed_cost'],6.46)
        self.assertEqual(len(run['trace']),5)
        self.assertTrue(run['review_required'])

    def test_no_write_tools_or_budget_bypass(self):
        worker=Investigator('gloves','EU',{},DemoResearch())
        self.assertIn('error',worker.execute('send_email',{}))
        self.assertIn('error',worker.execute('finish_review',{'reason':'done'}))
        for _ in range(2): worker.execute('research_offer',{'question':'resolve'})
        self.assertIn('error',worker.execute('research_offer',{'question':'again'}))
        self.assertEqual(worker.research_count,2)
        self.assertIn('error',worker.execute('inspect_offer',{'sql':'drop table'}))


if __name__=='__main__': unittest.main()
