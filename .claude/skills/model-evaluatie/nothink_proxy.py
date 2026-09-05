#!/usr/bin/env python3
"""Dun proxy'tje: forward naar Ollama (:11434) maar injecteer "think": false in
/api/chat en /api/generate. Zo krijgt olw (via --provider-url) non-thinking output.
Gebruik: python3 .claude/skills/model-evaluatie/nothink_proxy.py 11435
"""
import json
import sys
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

UPSTREAM = "http://127.0.0.1:11434"
INJECT_PATHS = ("/api/chat", "/api/generate")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _proxy(self, method):
        body = b""
        n = int(self.headers.get("Content-Length", 0) or 0)
        if n:
            body = self.rfile.read(n)
        if method == "POST" and self.path in INJECT_PATHS and body:
            try:
                obj = json.loads(body)
                obj["think"] = False
                body = json.dumps(obj).encode()
            except Exception:
                pass
        req = urllib.request.Request(UPSTREAM + self.path, data=body if body else None, method=method)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length", "connection"):
                req.add_header(k, v)
        if body:
            req.add_header("Content-Length", str(len(body)))
        try:
            up = urllib.request.urlopen(req, timeout=3600)
        except urllib.error.HTTPError as e:
            up = e
        except Exception as e:
            self.send_response(502); self.end_headers()
            self.wfile.write(str(e).encode()); return
        self.send_response(up.status)
        for k, v in up.headers.items():
            if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                self.send_header(k, v)
        self.send_header("Connection", "close")
        self.end_headers()
        while True:
            chunk = up.read(8192)
            if not chunk:
                break
            self.wfile.write(chunk); self.wfile.flush()

    def do_POST(self): self._proxy("POST")
    def do_GET(self): self._proxy("GET")
    def log_message(self, *a): pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
