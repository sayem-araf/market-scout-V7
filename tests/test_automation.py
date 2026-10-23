import json
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from automation_api import AutomationServer, investigate

class WorkflowTests(unittest.TestCase):
    def test_demo_brief_and_boundaries(self):
        result=investigate({'sku':'SKU-001','mode':'demo','request_id':'test'})
        self.assertEqual(result['purchasing_brief']['quantity'],310)
        self.assertEqual(result['supplier_research']['mode'],'offline-demo')
        self.assertFalse(result['research_added_to_quotations'])
        self.assertFalse(result['email_sent'])
        self.assertEqual(result['decision'],'HUMAN_REVIEW_REQUIRED')
        self.assertIn('DRAFT ONLY',result['inquiry_draft'])

    def test_reject_unknown_no_order_and_live_without_opt_in(self):
        for sku in ('SKU-002','UNKNOWN'):
            with self.assertRaises(ValueError):
                investigate({'sku':sku,'mode':'demo','request_id':'x'})
        with patch.dict('os.environ',{'MARKETSCOUT_ALLOW_LIVE':'0'}):
            with self.assertRaises(ValueError):
                investigate({'sku':'SKU-001','mode':'live','request_id':'x'})

    def test_adapter_auth_idempotency_and_conflict(self):
        server=AutomationServer(('127.0.0.1',0),'t'*32)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        def call(body=None,auth=True,origin=False):
            headers={'Content-Type':'application/json'}
            if auth: headers['Authorization']='Bearer '+'t'*32
            if origin: headers['Origin']='http://evil.invalid'
            request=Request(f'http://127.0.0.1:{server.server_port}/'+('investigate' if body else 'review'),data=json.dumps(body).encode() if body else None,headers=headers)
            try:
                with urlopen(request,timeout=10) as response: return response.status,json.load(response)
            except HTTPError as exc:
                with exc: return exc.code,json.load(exc)
        try:
            self.assertEqual(call(auth=False)[0],401)
            self.assertEqual(call(origin=True)[0],401)
            self.assertEqual(call()[1]['summary']['products'],20)
            body={'sku':'SKU-001','mode':'demo','request_id':'once'}
            with patch('automation_api.investigate',return_value={'decision':'HUMAN_REVIEW_REQUIRED'}) as run:
                self.assertEqual(call(body)[0],200)
                self.assertEqual(call(body)[0],200)
                self.assertEqual(run.call_count,1)
                self.assertEqual(call({**body,'sku':'SKU-003'})[0],409)
            with patch('automation_api.investigate',side_effect=RuntimeError('secret')) as run:
                failure={**body,'request_id':'failure'}
                self.assertEqual(call(failure)[0],502)
                self.assertNotIn('secret',json.dumps(call(failure)))
                self.assertEqual(run.call_count,1)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_export_defaults_manual_demo_no_sending(self):
        from pathlib import Path
        workflow=json.loads((Path(__file__).resolve().parents[1]/'n8n/marketscout-review.json').read_text())
        self.assertFalse(workflow['active'])
        self.assertTrue(any(n['type']=='n8n-nodes-base.manualTrigger' for n in workflow['nodes']))
        research=next(n for n in workflow['nodes'] if n['id']=='research')
        self.assertIn('mode: "demo"',research['parameters']['jsonBody'])
        self.assertFalse(any('email' in n['type'].lower() for n in workflow['nodes']))
