"""Authenticated local/container adapter for n8n. No email or purchase tools."""
import argparse
import hmac
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from inventory_review import build_review, draft_inquiry
from scout_agent import run_investigation, MODEL


def investigate(request, researcher=run_investigation):
    if not isinstance(request, dict) or set(request) != {'sku', 'mode', 'request_id'}:
        raise ValueError('Expected sku, mode and request_id')
    if request['mode'] not in ('demo', 'live'):
        raise ValueError('Mode must be demo or live')
    if not isinstance(request['request_id'], str) or not 1 <= len(request['request_id']) <= 100:
        raise ValueError('A request_id of 1–100 characters is required')
    if not isinstance(request['sku'], str):
        raise ValueError('SKU must be text')
    if request['mode'] == 'live' and (os.getenv('MARKETSCOUT_ALLOW_LIVE') != '1' or not os.getenv('GEMINI_API_KEY')):
        raise ValueError('Live research requires MARKETSCOUT_ALLOW_LIVE=1 and GEMINI_API_KEY on the adapter')
    report = build_review()
    item = next((row for row in report['items'] if row['sku'] == request['sku']), None)
    if item is None or item['suggested_quantity'] <= 0:
        raise ValueError('Choose a known SKU with a replenishment proposal')
    research = researcher(keyword=f"{item['name']}; sellable unit: {item['sellable_unit']}; currency: {item['currency']}",
        region='EU', vat_rate=float(item['vat_rate']), target_margin=float(item['target_margin']),
        fixed_costs=0, demo=request['mode'] == 'demo', api_key=os.getenv('GEMINI_API_KEY'),
        model=os.getenv('MARKETSCOUT_MODEL', MODEL))
    return {'request_id': request['request_id'], 'sku': item['sku'], 'mode': request['mode'],
        'snapshot_date': report['metadata']['as_of'], 'synthetic_inventory': True,
        'stages': ['Inventory rules evaluated', 'Supplier investigation completed', 'Human review brief prepared'],
        'purchasing_brief': item['handoff'], 'existing_quotation_review': {
            'action': item['action'], 'recommendation': item['recommendation'],
            'selected_quote_id': item['selected_quote_id'], 'quotations': item['quotations']},
        'supplier_research': research, 'inquiry_draft': draft_inquiry(item),
        'decision': 'HUMAN_REVIEW_REQUIRED', 'research_added_to_quotations': False,
        'review_checks': ['Confirm product specification, sellable unit and currency',
            'Verify source evidence and obtain a current binding quotation',
            'Confirm delivery date, MOQ, order multiples, validity and payment terms',
            'Recalculate using confirmed costs and current inventory before approval'],
        'limitations': ['Inventory and existing quotations are a fixed synthetic scenario',
            'Offline research is a fictional generic offer, not a product-specific quotation',
            'Live research is an unverified lead; it does not replace structured quotation checks'],
        'email_sent': False, 'purchase_approved': False}


class AutomationServer(ThreadingHTTPServer):
    def __init__(self, address, token):
        if len(token) < 32:
            raise ValueError('MARKETSCOUT_AUTOMATION_TOKEN must contain at least 32 characters')
        super().__init__(address, AutomationHandler)
        self.token = token
        self.execution_lock = threading.Lock()
        self.results = {}  # Bounded, process-local idempotency; no claim of durable audit history.


class AutomationHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, value):
        body = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def authenticated(self):
        # No browser endpoint or CORS; credentials live in n8n, never dashboard JS.
        return not self.headers.get('Origin') and hmac.compare_digest(
            self.headers.get('Authorization', '').encode(), ('Bearer ' + self.server.token).encode())

    def do_GET(self):
        if not self.authenticated():
            return self.send(401, {'error': 'Authentication required'})
        if self.path != '/review':
            return self.send(404, {'error': 'Not found'})
        self.send(200, build_review())

    def do_POST(self):
        if not self.authenticated():
            return self.send(401, {'error': 'Authentication required'})
        if self.path != '/investigate':
            return self.send(404, {'error': 'Not found'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2048 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Small JSON body required')
            request = json.loads(self.rfile.read(size))
            if not isinstance(request, dict) or set(request) != {'sku', 'mode', 'request_id'}:
                raise ValueError('Expected sku, mode and request_id')
            identifier = request['request_id']
            if not isinstance(identifier, str) or not 1 <= len(identifier) <= 100:
                raise ValueError('Invalid request_id')
        except (ValueError, TypeError):
            return self.send(400, {'error': 'Invalid request'})
        if not self.server.execution_lock.acquire(blocking=False):
            return self.send(409, {'error': 'Another investigation is running; do not start duplicate research'})
        try:
            previous = self.server.results.get(identifier)
            if previous:
                if previous[0] != request:
                    return self.send(409, {'error': 'request_id already used with different inputs'})
                return self.send(previous[1], previous[2])
            # Never evict and accidentally repeat a billable request using the same id.
            if len(self.server.results) >= 50:
                return self.send(503, {'error': 'Session capacity reached; export results before restarting'})
            try:
                result = investigate(request)
                status = 200
            except ValueError as exc:
                status, result = 400, {'error': str(exc)}
            except Exception:
                status, result = 502, {'error': 'Research failed; inspect configuration. No demo substituted. Use a new request_id only after reviewing the failure.'}
            self.server.results[identifier] = (request, status, result)
            self.send(status, result)
        finally:
            self.server.execution_lock.release()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    server = AutomationServer((args.host, args.port), os.getenv('MARKETSCOUT_AUTOMATION_TOKEN', ''))
    print(f'Automation adapter listening on {args.host}:{args.port}', flush=True)
    server.serve_forever()
