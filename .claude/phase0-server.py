#!/usr/bin/env python3
"""
phase0-server.py — Lokale HTTP-server voor Phase 0
===================================================
Serveert statische bestanden uit SERVE_DIR en accepteert
POST /skip requests om items expliciet te markeren als niet-interessant.

De skip-signalen worden weggeschreven naar skip_queue.jsonl in SCRIPT_DIR.
phase0-learn.py verwerkt die queue dagelijks en markeert items in score_log.jsonl.

Gebruik (via launchd):
    python3 phase0-server.py
"""

import http.server
import json
from pathlib import Path

SERVE_DIR  = Path.home() / ".local" / "share" / "phase0-serve"
SKIP_QUEUE = Path(__file__).parent / "skip_queue.jsonl"
PORT       = 8765


class Phase0Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_DIR), **kwargs)

    def do_POST(self):
        if self.path == "/skip":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body   = self.rfile.read(length)
                entry  = json.loads(body)
                if "url" not in entry:
                    self._respond(400, b"missing url")
                    return
                with SKIP_QUEUE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                self._respond(200, b"ok")
            except Exception as e:
                self._respond(500, str(e).encode())
        else:
            self._respond(404, b"not found")

    def _respond(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Onderdrukt ruis van GET-requests; logt alleen POSTs en fouten
        if args and (str(args[0]).startswith("POST") or (len(args) > 1 and str(args[1]) >= "400")):
            super().log_message(format, *args)


if __name__ == "__main__":
    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"phase0-server: luistert op http://localhost:{PORT}")
    print(f"Skip-queue:    {SKIP_QUEUE}")
    with http.server.ThreadingHTTPServer(("", PORT), Phase0Handler) as httpd:
        httpd.serve_forever()
