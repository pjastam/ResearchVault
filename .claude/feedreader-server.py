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
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SERVE_DIR    = Path.home() / ".local" / "share" / "feedreader-serve"
SCRIPT_DIR   = Path(__file__).parent
SKIP_QUEUE   = SCRIPT_DIR / "skip_queue.jsonl"
PORT         = 8765

# ── Zotero Web API ─────────────────────────────────────────────────────────────
def _load_api_key() -> str:
    """Laad de Zotero API key: eerst uit omgevingsvariabele, dan uit ~/.zprofile."""
    key = os.environ.get("ZOTERO_API_KEY", "")
    if key:
        return key
    # Fallback: lees direct uit ~/.zprofile (voor launchd dat geen shell-env erft)
    zprofile = Path.home() / ".zprofile"
    if zprofile.exists():
        for line in zprofile.read_text().splitlines():
            line = line.strip()
            if line.startswith("export ZOTERO_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

ZOTERO_API_KEY      = _load_api_key()
ZOTERO_USER_ID      = "24775"
ZOTERO_INBOX_KEY    = "N4MP46Y5"
ZOTERO_API_BASE     = f"https://api.zotero.org/users/{ZOTERO_USER_ID}"

_ITEM_TYPE_MAP = {
    "youtube":  "videoRecording",
    "podcast":  "podcast",
    "web":      "webpage",
}


def _add_to_zotero_inbox(
    url: str, title: str, source_type: str,
    action: str = "zotero", source: str = "", date: str = "",
) -> tuple[bool, str]:
    """
    Voegt een item toe aan Zotero _inbox via de Web API.
    Geeft (True, item_key) terug bij succes, (False, foutmelding) bij mislukking.
    """
    if not ZOTERO_API_KEY:
        return False, "ZOTERO_API_KEY niet ingesteld"

    item_type = _ITEM_TYPE_MAP.get(source_type, "webpage")

    # Creator-type en publisher-veld per itemtype
    creator_type, publisher_field = {
        "videoRecording": ("director",  "studio"),
        "podcast":        ("podcaster", "seriesTitle"),
    }.get(item_type, ("author", "websiteTitle"))

    item: dict = {
        "itemType":      item_type,
        "title":         title or url,
        "url":           url,
        "date":          date,
        "collections":   [ZOTERO_INBOX_KEY],
        "tags":          [{"tag": "✅" if action == "zotero" else "📖"}],
    }
    if source:
        item[publisher_field] = source
        item["creators"] = [{"creatorType": creator_type, "name": source}]

    payload = json.dumps([item]).encode("utf-8")

    req = urllib.request.Request(
        f"{ZOTERO_API_BASE}/items",
        data=payload,
        headers={
            "Zotero-API-Key":  ZOTERO_API_KEY,
            "Content-Type":    "application/json",
            "Zotero-API-Version": "3",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
            key  = next(iter(body.get("successful", {}).values()), {}).get("key", "")
            return True, key
    except Exception as e:
        return False, str(e)


class Phase0Handler(http.server.SimpleHTTPRequestHandler):

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
        import os
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
        params      = urllib.parse.parse_qs(query_string)
        url         = params.get("url",    [""])[0]
        action      = params.get("type",   [""])[0]
        title       = params.get("title",  [""])[0]
        source_type = params.get("stype",  ["web"])[0]
        source      = params.get("source", [""])[0]
        date        = params.get("date",   [""])[0]

        if not url or action not in ("zotero", "read", "skip"):
            self._respond_html(400, "<p>Ongeldige aanvraag.</p>")
            return

        ts = datetime.now(timezone.utc).isoformat()

        if action == "skip":
            self._append_queue(SKIP_QUEUE, {"url": url, "title": title, "timestamp": ts})
            self._respond_pixel(200)

        elif action in ("zotero", "read"):
            ok, _result = _add_to_zotero_inbox(url, title, source_type, action, source, date)
            self._respond_pixel(200 if ok else 500)

    @staticmethod
    def _append_queue(path: Path, entry: dict):
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _respond_action_page(self, message: str, url: str, color: str,
                              show_url: bool = False, zotero_key: str = ""):
        escaped_url = html.escape(url)
        extra = ""
        if zotero_key:
            zotero_link = f"zotero://select/library/items/{zotero_key}"
            extra = (
                f'<p style="margin-top:.75em;font-size:.85em;color:#555">'
                f'<a href="{html.escape(zotero_link)}" style="color:#2980b9">'
                f'Open in Zotero →</a></p>'
            )
        elif show_url:
            extra = (
                f'<p style="margin-top:.75em;font-size:.85em;color:#555">'
                f'<a href="{escaped_url}" style="color:#2980b9">{escaped_url}</a></p>'
            )
        body = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(message)}</title>
<style>body{{font-family:-apple-system,sans-serif;padding:2rem;max-width:500px;margin:auto}}</style>
</head><body>
<p style="font-size:1.4em;font-weight:600;color:{color}">{html.escape(message)}</p>
{extra}
<p style="margin-top:2em;font-size:.8em;color:#999">Je kunt dit tabblad sluiten.</p>
</body></html>"""
        self._respond_html(200, body)

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
