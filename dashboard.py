#!/usr/bin/env python3
"""Local-only MarketScout dashboard. No keys or arbitrary filesystem paths in the browser."""
import argparse
import json
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from market_scout import artifacts
from scout_agent import run_investigation, MODEL

ROOT = Path(__file__).resolve().parent
JOBS = {}
LOCK = threading.Lock()
POOL = ThreadPoolExecutor(max_workers=1)


def work(identifier, request):
    try:
        result = run_investigation(**request, api_key=os.getenv("GEMINI_API_KEY"), model=os.getenv("MARKETSCOUT_MODEL", MODEL))
        state = {"status": "complete", **result}
    except Exception:
        # Provider error bodies may include credentials or request details. Keep them out of the UI/log.
        state = {"status": "error", "error": "Research failed. Check that google-genai is installed, your API key/model supports search and function calling, and your network is available. No offline result has been substituted."}
    with LOCK:
        JOBS[identifier] = state


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def trusted(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host") == expected and self.headers.get("Origin", f"http://{expected}") == f"http://{expected}"

    def send(self, code, payload, content_type="application/json; charset=utf-8", download=None):
        body = json.dumps(payload, allow_nan=False).encode() if isinstance(payload, (dict, list)) else payload.encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if download:
            self.send_header("Content-Disposition", f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.trusted():
            return self.send(403, {"error": "Local origin required"})
        path = urlsplit(self.path).path
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
        if path in files:
            name, mime = files[path]
            return self.send(200, (ROOT / "static" / name).read_text(), mime)
        if path == "/api/config":
            return self.send(200, {"live_available": bool(os.getenv("GEMINI_API_KEY")), "model": os.getenv("MARKETSCOUT_MODEL", MODEL)})
        pieces = path.strip("/").split("/")
        if len(pieces) in (3, 4) and pieces[:2] == ["api", "runs"]:
            with LOCK:
                state = JOBS.get(pieces[2])
            if state is None:
                return self.send(404, {"error": "Run not found"})
            if len(pieces) == 3:
                return self.send(200, state)
            if state["status"] == "complete":
                outputs = artifacts(state["result"])
                outputs["investigation.json"] = json.dumps(state, indent=2, allow_nan=False)
                if pieces[3] in outputs:
                    return self.send(200, outputs[pieces[3]], "text/plain; charset=utf-8", pieces[3])
        self.send(404, {"error": "Not found"})

    def do_POST(self):
        if not self.trusted():
            return self.send(403, {"error": "Local origin required"})
        if self.path != "/api/runs":
            return self.send(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 8192 or self.headers.get("Content-Type") != "application/json":
                raise ValueError("Small JSON requests required")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or set(data) != {"keyword", "region", "vat_rate", "target_margin", "fixed_costs", "demo"}:
                raise ValueError("Invalid request fields")
            if not isinstance(data["keyword"], str) or not 2 <= len(data["keyword"].strip()) <= 300:
                raise ValueError("Enter a product between 2 and 300 characters")
            if not isinstance(data["region"], str) or not 1 <= len(data["region"]) <= 100 or type(data["demo"]) is not bool:
                raise ValueError("Invalid region or mode")
            from market_scout import calculate_margin, sample_record
            calculate_margin(sample_record(data["keyword"], data["region"]), data["vat_rate"], data["target_margin"], data["fixed_costs"])
            if not data["demo"] and not os.getenv("GEMINI_API_KEY"):
                raise ValueError("Set GEMINI_API_KEY on the server to enable live research")
            data["keyword"] = data["keyword"].strip()
            with LOCK:
                if any(job["status"] == "running" for job in JOBS.values()):
                    return self.send(409, {"error": "A research run is already in progress"})
                if len(JOBS) >= 20:
                    del JOBS[next(iter(JOBS))]
                identifier = uuid.uuid4().hex
                JOBS[identifier] = {"status": "running"}
            POOL.submit(work, identifier, data)
            self.send(202, {"id": identifier})
        except (ValueError, TypeError, KeyError) as exc:
            self.send(400, {"error": str(exc)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Open http://127.0.0.1:{args.port} — local-only; press Ctrl+C to stop", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
