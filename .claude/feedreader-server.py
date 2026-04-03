#!/usr/bin/env python3
"""
feedreader-server.py — Lokale HTTP-server voor de feedreader
=============================================================
Serveert statische bestanden uit SERVE_DIR en accepteert POST /skip requests
om items te markeren als afgewezen in de skip-queue.

Gebruik (via launchd):
    python3 feedreader-server.py
"""

import html
import http.server
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SERVE_DIR    = Path.home() / ".local" / "share" / "feedreader-serve"
SCRIPT_DIR   = Path(__file__).parent
SKIP_QUEUE   = SCRIPT_DIR / "skip_queue.jsonl"
READ_QUEUE   = SCRIPT_DIR / "read_queue.jsonl"
ZOTERO_QUEUE = SCRIPT_DIR / "zotero_queue.jsonl"
PORT         = 8765


class Phase0Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/action":
            self._handle_action(parsed.query)
        else:
            super().do_GET()

    def _handle_action(self, query_string: str):
        params = urllib.parse.parse_qs(query_string)
        url    = params.get("url", [""])[0]
        action = params.get("type", [""])[0]

        if not url or action not in ("zotero", "read", "skip"):
            self._respond_html(400, "<p>Ongeldige aanvraag.</p>")
            return

        ts    = datetime.now(timezone.utc).isoformat()
        entry = {"url": url, "timestamp": ts}

        if action == "skip":
            self._append_queue(SKIP_QUEUE, entry)
            self._respond_action_page("👎 Overgeslagen", url, "#c0392b")
        elif action == "read":
            self._append_queue(READ_QUEUE, entry)
            self._respond_action_page("📖 Toegevoegd aan leeslijst", url, "#1a7f4b")
        elif action == "zotero":
            self._append_queue(ZOTERO_QUEUE, entry)
            self._respond_action_page("✅ Gemarkeerd voor Zotero", url, "#2980b9", show_url=True)

    def _append_queue(self, path: Path, entry: dict):
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _respond_action_page(self, message: str, url: str, color: str, show_url: bool = False):
        escaped_url = html.escape(url)
        url_block = (
            f'<p style="margin-top:1em;font-size:.85em;color:#555">'
            f'Voeg toe via de Zotero-extensie: '
            f'<a href="{escaped_url}" style="color:#2980b9">{escaped_url}</a></p>'
        ) if show_url else ""
        body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(message)}</title>
<style>body{{font-family:-apple-system,sans-serif;padding:2rem;max-width:500px;margin:auto}}</style>
</head><body>
<p style="font-size:1.4em;font-weight:600;color:{color}">{html.escape(message)}</p>
{url_block}
<p style="margin-top:2em;font-size:.8em;color:#999">Je kunt dit tabblad sluiten.</p>
</body></html>"""
        self._respond_html(200, body)

    def _respond_html(self, code: int, body: str):
        encoded = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

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
        if args and (
            str(args[0]).startswith("POST")
            or (len(args) > 1 and str(args[1]) >= "400")
        ):
            super().log_message(format, *args)


if __name__ == "__main__":
    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"feedreader-server: luistert op http://localhost:{PORT}")
    print(f"Skip-queue: {SKIP_QUEUE}")
    with http.server.ThreadingHTTPServer(("", PORT), Phase0Handler) as httpd:
        httpd.serve_forever()
