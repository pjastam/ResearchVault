#!/usr/bin/env python3
"""
feedreader-server.py — Lokale HTTP-server voor de feedreader
=============================================================
Serveert statische bestanden uit SERVE_DIR en handelt GET /action?type=skip
requests af om items toe te voegen aan de skip-queue (negatief leersignaal).

Biedt ook een REST API voor de inbox-review HTML-pagina (/inbox):
  GET  /inbox               → inbox.html
  GET  /api/inbox/items     → gecombineerde scores + Zotero metadata
  GET  /api/inbox/summary/{key} → samenvatting van één item (async)
  GET  /api/inbox/jobs      → status van achtergrond-jobs
  POST /api/inbox/go        → bouw raw-bundle + olw ingest (achtergrond)
  POST /api/inbox/nogo      → verwijder uit _inbox (direct)
  POST /api/inbox/summarize → vraag samenvatting aan (achtergrond)

Gebruik (via launchd):
    python3 feedreader-server.py
"""

import http.server
import json
import os
import queue
import re
import subprocess
import threading
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

SERVE_DIR  = Path.home() / ".local" / "share" / "feedreader-serve"
SCRIPT_DIR = Path(__file__).parent
SKIP_QUEUE = SCRIPT_DIR / "skip_queue.jsonl"
PORT       = int(os.environ.get("FEEDREADER_PORT", "8765"))   # override voor test-instance

# Zotero keys zijn altijd 8 hoofdletters/cijfers
_KEY_RE = re.compile(r'^[A-Z0-9]{8}$')

VAULT_ROOT = Path(__file__).resolve().parent.parent
VAULT_DIR  = VAULT_ROOT / "vault"     # symlink → ResearchVault/vault/
PYTHON     = Path("/Users/pietstam/.local/share/uv/tools/zotero-mcp-server/bin/python3")
INBOX_DIR  = VAULT_ROOT / "vault" / ".cache"   # temp-input (fase-2 previews e.d.); gitignored
OLW        = Path("/Users/pietstam/.local/bin/olw")   # Fase C: Go → build-bundle → olw ingest

# Achtergrond job-queue voor build-zotero-bundle.py (+olw ingest) en summarize_item.py
_job_queue  = queue.Queue()
_job_status = {}   # key → {"status": "pending"|"running"|"done"|"error", "path": ..., "error": ...}
_job_lock   = threading.Lock()


def _inbox_worker():
    """Daemon-thread: verwerkt jobs uit _job_queue sequentieel."""
    while True:
        job = _job_queue.get()
        key = job["key"]
        cmd = job["cmd"]
        with _job_lock:
            _job_status[key] = {"status": "running", "path": None, "error": None}
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300,
                cwd=str(VAULT_DIR),
                # ZOTERO_LOCAL=true forceert lokale Zotero API in fetch-fulltext.py,
                # die anders de Web API kiest zodra ZOTERO_API_KEY uit vault/.env geladen is.
                env={**os.environ, "ZOTERO_ACCESS": "auto", "ZOTERO_LOCAL": "true"},
            )
            out = result.stdout.strip()
            data = json.loads(out) if out else {}
            if result.returncode == 0 and data.get("status") == "ok":
                bundle_path = data.get("path")
                # Fase C: Go-jobs bouwen een raw-bundle → daarna olw ingest (concept-
                # extractie, GEEN compile). Andere jobs (summarize) slaan dit over.
                if job.get("ingest") and bundle_path:
                    abs_bundle = str(VAULT_ROOT / bundle_path)
                    ingest = subprocess.run(
                        [str(OLW), "ingest", abs_bundle, "--vault", str(VAULT_DIR),
                         "--fast-model", "mistral-small:22b"],
                        capture_output=True, text=True, timeout=1800,
                        cwd=str(VAULT_DIR), env={**os.environ},
                    )
                    if ingest.returncode != 0:
                        with _job_lock:
                            _job_status[key] = {
                                "status": "error", "path": bundle_path,
                                "error": "olw ingest faalde: "
                                         + (ingest.stderr.strip()[-300:] or "onbekend"),
                            }
                        continue   # niet uit _inbox halen als ingest faalde
                with _job_lock:
                    _job_status[key] = {"status": "done", "path": bundle_path, "error": None}
                # Verwijder item uit Zotero _inbox na succes — alleen go-jobs met een echte
                # item-key; summarize heeft er geen → item blijft in _inbox voor de beslissing.
                item_key = job.get("item_key")
                if item_key:
                    subprocess.run(
                        [str(PYTHON), str(SCRIPT_DIR / "zotero-remove-from-inbox.py"), "--", item_key],
                        capture_output=True, text=True, timeout=30,
                        cwd=str(VAULT_DIR),
                        env={**os.environ, "ZOTERO_ACCESS": "web"},
                    )
            else:
                err = data.get("message") or result.stderr.strip() or "onbekende fout"
                with _job_lock:
                    _job_status[key] = {"status": "error", "path": None, "error": err}
        except subprocess.TimeoutExpired:
            with _job_lock:
                _job_status[key] = {"status": "error", "path": None, "error": "timeout na 300s"}
        except Exception as exc:
            with _job_lock:
                _job_status[key] = {"status": "error", "path": None, "error": str(exc)}
        finally:
            _job_queue.task_done()


# Start worker als daemon zodat hij stopt als het hoofdproces stopt
_worker_thread = threading.Thread(target=_inbox_worker, daemon=True)
_worker_thread.start()


class FeedreaderHandler(http.server.SimpleHTTPRequestHandler):

    _FEED_FILES = ("filtered-webpage.xml", "filtered-youtube.xml", "filtered-podcast.xml")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_DIR), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        if path == "/action":
            self._handle_action(parsed.query)
        elif path == "/inbox":
            self._serve_inbox_html()
        elif path == "/api/inbox/items":
            self._handle_inbox_items()
        elif path.startswith("/api/inbox/summary/"):
            key = path[len("/api/inbox/summary/"):]
            self._handle_inbox_summary(key)
        elif path == "/api/inbox/jobs":
            self._handle_inbox_jobs()
        elif path.endswith(".xml"):
            self._serve_xml(path)
        else:
            super().do_GET()

    def do_POST(self):
        # CSRF-bescherming: vereis application/json en blokkeer cross-origin verzoeken.
        # Origin mag ontbreken (programmatische aanroepen), maar als die er is moet hij
        # overeenkomen met de Host-header (same-server; werkt ook voor iPad via Tailscale IP).
        ctype = self.headers.get("Content-Type", "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._respond_json(403, {"error": "forbidden"})
            return
        origin = self.headers.get("Origin", "")
        host   = self.headers.get("Host", "")
        if origin and origin != f"http://{host}":
            self._respond_json(403, {"error": "forbidden"})
            return

        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length) if length else b""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._respond_json(400, {"error": "Ongeldige JSON"})
            return

        if path == "/api/inbox/go":
            self._handle_go(data)
        elif path == "/api/inbox/nogo":
            self._handle_nogo(data)
        elif path == "/api/inbox/summarize":
            self._handle_summarize(data)
        else:
            self._respond_json(404, {"error": "Niet gevonden"})

    def do_OPTIONS(self):
        path = urllib.parse.urlparse(self.path).path
        self.send_response(200)
        if not path.startswith("/api/inbox"):
            # Niet-API paden (bijv. /action GIF): wildcard OK (GET-only, geen subprocessen)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        # Geen CORS-headers voor /api/inbox/* — inbox.html is same-origin
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ── Inbox HTML ────────────────────────────────────────────────────────────

    def _serve_inbox_html(self):
        html_path = SCRIPT_DIR / "inbox.html"
        if not html_path.exists():
            self._respond_html(404, "<p>inbox.html niet gevonden.</p>")
            return
        data = html_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ── Inbox API ─────────────────────────────────────────────────────────────

    def _handle_inbox_items(self):
        """Combineert index-score --json met zotero-inbox --json output."""
        try:
            # Scores ophalen (werkt zonder Zotero desktop via SQLite-kopie)
            score_result = subprocess.run(
                [str(PYTHON), str(SCRIPT_DIR / "index-score.py"), "--json"],
                capture_output=True, text=True, timeout=60,
            )
            scores_by_key = {}
            if score_result.returncode == 0 and score_result.stdout.strip():
                for item in json.loads(score_result.stdout):
                    scores_by_key[item["key"]] = item

            # Metadata ophalen (vereist Zotero desktop; auto-start via ZOTERO_ACCESS=auto)
            inbox_result = subprocess.run(
                [str(PYTHON), str(SCRIPT_DIR / "zotero-inbox.py"), "--json"],
                capture_output=True, text=True, timeout=90,
                cwd=str(VAULT_DIR),
                env={**os.environ, "ZOTERO_ACCESS": "auto"},
            )
            if inbox_result.returncode != 0:
                self._respond_json(503, {"error": "Zotero niet bereikbaar", "detail": inbox_result.stderr})
                return

            inbox_items = json.loads(inbox_result.stdout) if inbox_result.stdout.strip() else []

            # Combineren: metadata uit Zotero, score uit index-score
            combined = []
            for item in inbox_items:
                key = item["key"]
                score_data = scores_by_key.get(key, {})
                combined.append({
                    "key":        key,
                    "title":      item["title"],
                    "type":       item["type"],
                    "author":     item["author"],
                    "year":       item["year"],
                    "tags":       item["tags"],
                    "url":        item["url"],
                    "abstract":   item.get("abstract", ""),
                    "zotero_url": f"zotero://select/library/items/{key}",
                    "score":      score_data.get("score"),
                    "label":      score_data.get("label"),
                })

            # Sorteer: gescoorde items eerste (op score desc), dan ongescoorde
            combined.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0)))
            self._respond_json(200, combined)

        except subprocess.TimeoutExpired:
            self._respond_json(504, {"error": "Timeout bij ophalen inbox"})
        except Exception as exc:
            self._respond_json(500, {"error": str(exc)})

    def _handle_inbox_summary(self, key: str):
        """Leest een al-gegenereerde samenvatting uit .cache/_summary_{key}.md."""
        if not _KEY_RE.fullmatch(key):
            self._respond_json(400, {"error": "Ongeldige key"})
            return
        summary_path = INBOX_DIR / f"_summary_{key}.md"
        if not summary_path.exists():
            self._respond_json(404, {"status": "not_found"})
            return
        text = summary_path.read_text(encoding="utf-8")
        self._respond_json(200, {"status": "ready", "text": text})

    def _handle_inbox_jobs(self):
        """Geeft de huidige status van alle achtergrond-jobs terug."""
        with _job_lock:
            snapshot = dict(_job_status)
        counts = {"pending": 0, "running": 0, "done": 0, "error": 0}
        for v in snapshot.values():
            counts[v["status"]] = counts.get(v["status"], 0) + 1
        self._respond_json(200, {"jobs": snapshot, "counts": counts})

    def _handle_go(self, data: dict):
        """Fase C: bouwt via build-zotero-bundle.py een raw-bundle + olw ingest (geen compile).

        Vervangt de oude process_item.py→literature/-tak (die tak is in Fase F verwijderd).
        De wiki-draft ontstaat later via een batch-compile; `olw review` is de kwaliteitsgate.
        """
        key = data.get("key", "").strip()
        if not _KEY_RE.fullmatch(key):
            self._respond_json(400, {"error": "Ongeldige key"})
            return

        if not data.get("title", "").strip():
            self._respond_json(400, {"error": "title is verplicht voor Go"})
            return

        with _job_lock:
            existing = _job_status.get(key, {}).get("status")
        if existing in ("pending", "running"):
            self._respond_json(200, {"queued": False, "reason": "al in wachtrij"})
            return

        # build-zotero-bundle.py haalt zelf alle metadata uit Zotero → alleen --item-key nodig.
        cmd = [str(PYTHON), str(SCRIPT_DIR / "build-zotero-bundle.py"), "--item-key", key]

        with _job_lock:
            _job_status[key] = {"status": "pending", "path": None, "error": None}
        _job_queue.put({"key": key, "item_key": key, "cmd": cmd, "ingest": True})
        self._respond_json(200, {"queued": True})

    def _handle_nogo(self, data: dict):
        """Verwijdert een item uit de Zotero _inbox (direct, synchroon)."""
        key = data.get("key", "").strip()
        if not _KEY_RE.fullmatch(key):
            self._respond_json(400, {"error": "Ongeldige key"})
            return
        try:
            result = subprocess.run(
                [str(PYTHON), str(SCRIPT_DIR / "zotero-remove-from-inbox.py"), "--", key],
                capture_output=True, text=True, timeout=30,
                cwd=str(VAULT_DIR),
                env={**os.environ, "ZOTERO_ACCESS": "web"},
            )
            if result.returncode == 0:
                self._respond_json(200, {"removed": True})
            else:
                self._respond_json(500, {"removed": False, "error": result.stderr.strip()})
        except subprocess.TimeoutExpired:
            self._respond_json(504, {"error": "Timeout bij verwijderen"})
        except Exception as exc:
            self._respond_json(500, {"error": str(exc)})

    def _handle_summarize(self, data: dict):
        """Voegt een summarize_item.py job toe aan de achtergrond-queue."""
        key = data.get("key", "").strip()
        if not _KEY_RE.fullmatch(key):
            self._respond_json(400, {"error": "Ongeldige key"})
            return

        with _job_lock:
            existing = _job_status.get(f"sum_{key}", {}).get("status")
        if existing in ("pending", "running"):
            self._respond_json(200, {"queued": False, "reason": "al in wachtrij"})
            return

        item_type = data.get("type", "paper")
        cmd = [
            str(PYTHON), str(SCRIPT_DIR / "summarize_item.py"),
            "--item-key", key, "--type", item_type,
        ]
        if data.get("title"):
            cmd += ["--title", data["title"]]
        if data.get("authors"):
            cmd += ["--authors", data["authors"]]
        if data.get("year"):
            cmd += ["--year", str(data["year"])]
        if data.get("abstract"):
            cmd += ["--abstract", data["abstract"]]

        job_key = f"sum_{key}"
        with _job_lock:
            _job_status[job_key] = {"status": "pending", "path": None, "error": None}
        _job_queue.put({"key": job_key, "cmd": cmd})
        self._respond_json(200, {"queued": True})

    # ── Bestaande routes ──────────────────────────────────────────────────────

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

    # ── Response helpers ──────────────────────────────────────────────────────

    def _respond_json(self, code: int, payload):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        # Geen ACAO-header: inbox.html is same-origin (zelfde poort 8765)
        self.end_headers()
        self.wfile.write(encoded)

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

    def log_message(self, format, *args):
        if args and (
            str(args[0]).startswith("POST")
            or (len(args) > 1 and str(args[1]) >= "400")
            or (len(args) > 1 and str(args[1]) == "200" and any(f in str(args[0]) for f in self._FEED_FILES))
        ):
            super().log_message(format, *args)


if __name__ == "__main__":
    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    print(f"feedreader-server: luistert op http://localhost:{PORT}")
    print(f"Skip-queue: {SKIP_QUEUE}")
    with http.server.ThreadingHTTPServer(("", PORT), FeedreaderHandler) as httpd:
        httpd.serve_forever()
