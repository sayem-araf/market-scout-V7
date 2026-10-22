"""Exercise the real SDK types with mocked transport: no paid or network calls."""
import json
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch
try:
    from google.genai import types
except ImportError:
    types = None
from market_scout import sample_record
from scout_agent import run_investigation, GroundedResearch


@unittest.skipIf(types is None, 'Install requirements.txt for SDK adapter checks')
class SDKTests(unittest.TestCase):
    def test_live_tool_loop_and_grounded_response_parsing(self):
        record = asdict(sample_record('gloves'))
        del record['product_keyword']
        record['evidence']=[{'field': field,'url':'https://example.com/quote','note':'Test evidence'} for field in ('wholesale_price','retail_benchmark','moq','shipping_per_unit','duty_per_unit')]
        calls=[]
        def generate(**kwargs):
            config=kwargs['config']
            calls.append(config.model_dump(mode='json'))
            if config.tools[0].google_search is not None:
                return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role='model', parts=[types.Part.from_text(text=json.dumps(record))]))])
            count=sum('function_declarations' in (item.get('tools') or [{}])[0] and bool((item.get('tools') or [{}])[0].get('function_declarations')) for item in calls)
            name,args=[('research_offer',{'question':'find one offer'}),('inspect_offer',{}),('finish_review',{'reason':'Human verification needed'})][count-1]
            return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role='model',parts=[types.Part.from_function_call(name=name,args=args)]))])
        client=SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        with patch('scout_agent.sdk_client',return_value=(client,types)):
            result=run_investigation('gloves',api_key='unused-mock-key')
        self.assertEqual(result['mode'],'live-gemini')
        self.assertEqual([s['tool'] for s in result['trace']],['research_offer','inspect_offer','finish_review'])
        self.assertEqual(result['result']['landed_cost'],6.46)
        self.assertEqual(len(calls),4)

    def test_uncited_prices_are_not_calculated(self):
        record=asdict(sample_record('gloves'))
        del record['product_keyword']
        record['evidence']=[]
        client=SimpleNamespace(models=SimpleNamespace(generate_content=lambda **_:types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role='model',parts=[types.Part.from_text(text=json.dumps(record))]))])))
        with patch('scout_agent.sdk_client',return_value=(client,types)):
            offer,evidence,sources=GroundedResearch('unused').research('gloves','EU','find')
        self.assertIsNone(offer.wholesale_price)
        self.assertIsNone(offer.shipping_per_unit)


if __name__=='__main__':unittest.main()
