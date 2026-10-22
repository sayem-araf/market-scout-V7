import http.client
import json
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import dashboard


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),dashboard.Handler)
        cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self,path,method='GET',payload=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        body=json.dumps(payload) if payload is not None else None
        connection.request(method,path,body=body,headers=headers or ({'Content-Type':'application/json'} if body else {}))
        response=connection.getresponse()
        status,headers,body=response.status,dict(response.getheaders()),response.read()
        connection.close()
        return status,headers,body

    def test_full_demo_and_download(self):
        status,_,body=self.request('/api/runs','POST',dict(keyword='gloves',region='EU',vat_rate=.2,target_margin=.6,fixed_costs=500,demo=True))
        self.assertEqual(status,202)
        identifier=json.loads(body)['id']
        for _ in range(100):
            _,_,body=self.request('/api/runs/'+identifier)
            result=json.loads(body)
            if result['status']!='running':break
            time.sleep(.01)
        self.assertEqual(result['status'],'complete')
        self.assertEqual(result['result']['decision'],'NO-GO')
        status,headers,body=self.request('/api/runs/'+identifier+'/catalog_entry.csv')
        self.assertEqual(status,200)
        self.assertIn('attachment',headers['Content-Disposition'])
        self.assertIn(b'NO-GO',body)

    def test_host_origin_and_path_boundaries(self):
        self.assertEqual(self.request('/api/config',headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('/api/config',headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.request('/../../.env')[0],404)
        self.assertEqual(self.request('/scout_agent.py')[0],404)

    def test_invalid_requests_and_no_key_live_mode(self):
        payload=dict(keyword='gloves',region='EU',vat_rate=float('nan'),target_margin=.6,fixed_costs=500,demo=True)
        self.assertEqual(self.request('/api/runs','POST',payload)[0],400)
        payload.update(vat_rate=.2,demo=False)
        with patch.dict('os.environ',{},clear=True):
            status,_,body=self.request('/api/runs','POST',payload)
        self.assertEqual(status,400)
        self.assertIn(b'GEMINI_API_KEY',body)


if __name__=='__main__':unittest.main()
