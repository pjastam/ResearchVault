#!/usr/bin/env python3
"""
feedreader-server.py — Lokale HTTP-server voor de feedreader
=============================================================
Serveert statische bestanden uit SERVE_DIR en handelt GET /action?type=skip
requests af om items toe te voegen aan de skip-queue (negatief leersignaal).

Zotero-acties (✅/📖) zijn verwijderd: NNW-sterren dienen nu als positief
signaal via de FreshRSS GReader API (zie feedreader-learn.py).

Gebruik (via launchd):
    python3 feedreader-server.py
"""

import http.server
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SERVE_DIR  = Path.home() / ".local" / "share" / "feedreader-serve"
SCRIPT_DIR = Path(__file__).parent
SKIP_QUEUE = SCRIPT_DIR / "skip_queue.jsonl"
PORT       = 8765


class FeedreaderHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/action":
            self._handle_action(parsed.query)
        elif parsed.path.endswith(".xml"):
            self._serve_xml(parsed.path)
        else:
            super().do_GET()

    def _serve_xml(self, path: str):
        """Serveert XML-feeds altijd als volledige respons (nooit 304)."""
        file_path = SERVE_DIR / path.lstrip("/")
        if not file_path.exists():
            self.send_error(404)
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _handle_action(self, query_string: str):
        params = urllib.parse.parse_qs(query_string)
        url    = params.get("url",   [""])[0]
        action = params.get("type",  [""])[0]
        title  = params.get("title", [""])[0]

        if not url or action != "skip":
            self._respond_html(400, "<p>Ongeldige aanvraag.</p>")
            return

        ts = datetime.now(timezone.utc).isoformat()
        with SKIP_QUEUE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"url": url, "title": title, "timestamp": ts},
                               ensure_ascii=False) + "\n")
        self._respond_pixel(200)

    def _respond_pixel(self, code: int):
        """Retourneert een 1×1 transparante GIF — onload = succes, onerror = fout."""
        gif = (b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
               b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00'
               b'\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b')
        self.send_response(code)
        self.send_header("Content-Type", "image/gif")
        self.send_header("Content-Length", str(len(gif)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(gif)

    def _respond_html(self, code: int, body: str):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        if args and (
            str(args[0]).startswith("POST")
            or (len(args) > 1 and str(args[1]) >= "400")
        ):
            super().log_message(format, *args)


if __name__ == "__main__":
    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"feedreader-server: luistert op http://localhost:{PORT}")
    print(f"Skip-queue: {SKIP_QUEUE}")
    with http.server.ThreadingHTTPServer(("", PORT), FeedreaderHandler) as httpd:
        httpd.serve_forever()
