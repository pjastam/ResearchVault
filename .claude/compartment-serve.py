#!/usr/bin/env python3
"""compartment-serve.py — Fase G/G6: iPad thin-client voor een vertrouwelijk compartiment.

Read-only viewer + draft-review over het TAILNET (nooit Funnel). Rendert de compartiment-
wiki/ + authoring/ en de pending olw-drafts van markdown → HTML, zodat je ze op iPad/iPhone
kunt LEZEN en drafts kunt goedkeuren/afwijzen — zónder dat de bronbestanden de Mac verlaten
(olw/Obsidian draaien toch niet op iPad).

Veiligheid (structureel, niet policy):
- Bindt op het TAILNET-IP (`tailscale ip -4`), NIET 0.0.0.0/localhost → alleen bereikbaar
  vanaf jouw eigen Tailscale-apparaten. Nooit funnelen: er luistert niets op de publieke
  interface, dus zelfs een per ongeluk toegevoegde Funnel-regel exposet niets.
- Path-traversal-safe: serveert uitsluitend .md-bestanden BINNEN de compartiment-root.
- Read-only content; POST /approve|/reject roept alleen `olw approve`/`olw reject` aan op
  drafts van DÍT compartiment. De beslissing reist terug, de inhoud blijft op de Mac.
- Privacy: rendert lokaal, serveert over Tailnet; print nooit inhoud naar stdout (alleen
  beknopte request-logs). olw-uitvoer → JSON-status, nooit draft-inhoud.

On-demand: `compartment-serve.py <naam>`; Ctrl-C stopt. GEEN daemon.

Gebruik:
    compartment-serve.py <naam> [--host IP] [--port 8766]
    # --host 127.0.0.1 voor lokale test; default = Tailnet-IP
"""

import argparse
import html as html_mod
import json
import re
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

CONFIDENTIAL_ROOT = Path.home() / "Confidential"
OLW = "/Users/pietstam/.local/bin/olw"
DRAFT_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.md$")   # whitelist draftnamen (XSS/injectie-hardening)

COMPARTMENT: Path = Path()          # gezet in main()
NAME = ""


# ── Minimale markdown → HTML (dependency-loos) ──────────────────────────────────

def _inline(s: str) -> str:
    """Inline-opmaak op reeds ge-escapete tekst."""
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    # [tekst](url)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    # [[wikilink]] → /find?name= (server zoekt het .md-bestand in het compartiment)
    def _wiki(m):
        target = m.group(1).split("|")[0].strip()
        label = m.group(1).split("|")[-1].strip()
        return f'<a href="/find?name={html_mod.escape(target)}">{html_mod.escape(label)}</a>'
    s = re.sub(r"\[\[([^\]]+)\]\]", _wiki, s)
    return s


def md_to_html(text: str) -> str:
    """Genoeg-voor-lezen renderer: escape eerst (XSS-veilig), dan blokken + inline."""
    out, in_code, in_list = [], False, False
    for raw in text.split("\n"):
        if raw.strip().startswith("```"):
            if in_code:
                out.append("</pre>"); in_code = False
            else:
                if in_list: out.append("</ul>"); in_list = False
                out.append("<pre>"); in_code = True
            continue
        if in_code:
            out.append(html_mod.escape(raw)); continue
        line = html_mod.escape(raw)
        m = re.match(r"(#{1,6})\s+(.*)", line)
        if m:
            if in_list: out.append("</ul>"); in_list = False
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2))}</h{lvl}>"); continue
        if re.match(r"\s*[-*]\s+", line):
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\s*[-*]\s+', '', line))}</li>"); continue
        if in_list: out.append("</ul>"); in_list = False
        if not line.strip():
            continue
        if re.match(r"\s*---+\s*$", raw):
            out.append("<hr>"); continue
        out.append(f"<p>{_inline(line)}</p>")
    if in_list: out.append("</ul>")
    if in_code: out.append("</pre>")
    return "\n".join(out)


# ── Paden ───────────────────────────────────────────────────────────────────────

def safe_md(relpath: str):
    """Los relpath op binnen de compartiment-root; alleen .md; geen traversal. None = ongeldig."""
    try:
        target = (COMPARTMENT / relpath).resolve()
    except Exception:
        return None
    root = COMPARTMENT.resolve()
    if root != target and root not in target.parents:
        return None                                    # buiten de compartiment-root
    if target.suffix != ".md" or not target.is_file():
        return None
    return target


def find_md(name: str):
    """Zoek <name>.md (case-insensitief) ergens in het compartiment (voor [[wikilinks]])."""
    stem = name.lower().removesuffix(".md")
    for p in COMPARTMENT.rglob("*.md"):
        if p.stem.lower() == stem:
            return p
    return None


def list_md(subdir: str):
    d = COMPARTMENT / subdir
    if not d.is_dir():
        return []
    return sorted(p.relative_to(COMPARTMENT).as_posix()
                  for p in d.rglob("*.md") if ".drafts" not in p.parts)


def list_drafts():
    d = COMPARTMENT / "wiki" / ".drafts"
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.md") if DRAFT_NAME_RE.match(p.name))


# ── HTML-wrapper (iPad-vriendelijk) ─────────────────────────────────────────────

def page(title: str, body: str) -> bytes:
    css = ("body{font-family:-apple-system,system-ui,sans-serif;max-width:820px;margin:0 auto;"
           "padding:1rem 1.2rem;line-height:1.55;color:#1a1a1a}a{color:#0b6bcb}"
           "pre{background:#f4f4f4;padding:.7rem;overflow-x:auto;border-radius:6px}"
           "code{background:#f4f4f4;padding:.1rem .3rem;border-radius:4px}"
           "h1,h2,h3{line-height:1.25}.muted{color:#777}.draft{border:1px solid #ddd;"
           "border-radius:8px;padding:1rem;margin:1rem 0}button{font-size:1rem;padding:.5rem 1rem;"
           "margin-right:.5rem;border-radius:6px;border:1px solid #bbb;background:#fff}"
           "button.go{background:#0b6bcb;color:#fff;border-color:#0b6bcb}"
           "@media(prefers-color-scheme:dark){body{background:#1a1a1a;color:#e8e8e8}"
           "pre,code{background:#2a2a2a}a{color:#5aa9ff}.draft{border-color:#444}"
           "button{background:#2a2a2a;color:#e8e8e8;border-color:#555}}")
    doc = (f"<!doctype html><html><head><meta charset='utf-8'>"
           f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
           f"<title>{html_mod.escape(title)}</title><style>{css}</style></head><body>{body}"
           f"<hr><p class='muted'>compartiment: {html_mod.escape(NAME)} · thin-client (Tailnet-only)</p>"
           f"</body></html>")
    return doc.encode("utf-8")


# ── HTTP-handler ─────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):        # alleen methode+pad, nooit inhoud
        sys.stderr.write(f"{self.command} {self.path.split('?')[0]}\n")

    def _send(self, body: bytes, status=200, ctype="text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, status=200):
        self._send(json.dumps(obj).encode(), status, "application/json")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == "/":
            return self._index()
        if u.path == "/view":
            return self._view(q.get("path", [""])[0])
        if u.path == "/find":
            p = find_md(q.get("name", [""])[0])
            return self._render_file(p) if p else self._send(page("Niet gevonden",
                "<p>Geen pagina gevonden.</p>"), 404)
        if u.path == "/drafts":
            return self._drafts()
        self._send(page("404", "<p>Niet gevonden.</p>"), 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path not in ("/approve", "/reject"):
            return self._json({"status": "error", "error": "onbekend endpoint"}, 404)
        length = int(self.headers.get("Content-Length", 0))
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"status": "error", "error": "ongeldige body"}, 400)
        fname = Path(data.get("file", "")).name
        if not DRAFT_NAME_RE.match(fname):
            return self._json({"status": "error", "error": "ongeldige draftnaam"}, 400)
        draft = COMPARTMENT / "wiki" / ".drafts" / fname
        if not draft.is_file():
            return self._json({"status": "error", "error": "draft niet gevonden"}, 404)
        cmd = [OLW, "approve" if u.path == "/approve" else "reject", str(draft),
               "--vault", str(COMPARTMENT)]
        if u.path == "/reject" and data.get("feedback"):
            cmd += ["--feedback", str(data["feedback"])]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120)   # inhoud NIET tonen
            ok = proc.returncode == 0
            return self._json({"status": "ok" if ok else "error",
                               "action": u.path.strip("/"), "returncode": proc.returncode})
        except Exception as exc:
            return self._json({"status": "error", "error": str(exc)}, 500)

    # ── pagina's ──
    def _index(self):
        def links(items):
            return "".join(f"<li><a href='/view?path={html_mod.escape(p)}'>"
                           f"{html_mod.escape(p)}</a></li>" for p in items) or "<li class='muted'>—</li>"
        drafts = list_drafts()
        body = (f"<h1>{html_mod.escape(NAME)}</h1>"
                f"<h2>Drafts ter review ({len(drafts)})</h2>"
                + (f"<p><a href='/drafts'>→ {len(drafts)} draft(s) beoordelen</a></p>"
                   if drafts else "<p class='muted'>Geen pending drafts.</p>")
                + f"<h2>wiki/</h2><ul>{links(list_md('wiki'))}</ul>"
                + f"<h2>authoring/</h2><ul>{links(list_md('authoring'))}</ul>")
        self._send(page(NAME, body))

    def _view(self, relpath):
        p = safe_md(relpath)
        return self._render_file(p) if p else self._send(
            page("Geweigerd", "<p>Ongeldig of buiten het compartiment.</p>"), 403)

    def _render_file(self, p: Path):
        rel = p.relative_to(COMPARTMENT).as_posix()
        body = (f"<p><a href='/'>← index</a></p><h1>{html_mod.escape(rel)}</h1>"
                + md_to_html(p.read_text(encoding="utf-8", errors="replace")))
        self._send(page(rel, body))

    def _drafts(self):
        drafts = list_drafts()
        blocks = []
        for d in drafts:
            esc = html_mod.escape(d.name)   # filename ALLEEN in een data-attribuut, nooit in JS-context
            blocks.append(
                f"<div class='draft' data-file=\"{esc}\"><h2>{esc}</h2>"
                + md_to_html(d.read_text(encoding="utf-8", errors="replace"))
                + "<p><button class='go' data-action='approve'>✓ Approve</button>"
                + "<button data-action='reject'>✗ Reject</button></p></div>")
        # Handlers via addEventListener + dataset (geen filename in de JS-broncode → geen XSS).
        js = ("<script>document.querySelectorAll('button[data-action]').forEach(function(b){"
              "b.addEventListener('click',function(){var div=b.closest('.draft'),"
              "f=div.dataset.file,a=b.dataset.action,"
              "fb=a==='reject'?(prompt('Reden (optioneel):')||''):'';"
              "fetch('/'+a,{method:'POST',headers:{'Content-Type':'application/json'},"
              "body:JSON.stringify({file:f,feedback:fb})}).then(r=>r.json()).then(function(j){"
              "div.style.opacity=j.status==='ok'?0.4:1;"
              "if(j.status!=='ok')alert('Fout: '+(j.error||j.returncode));});});});</script>")
        body = "<p><a href='/'>← index</a></p><h1>Drafts</h1>" + ("".join(blocks)
               if blocks else "<p class='muted'>Geen drafts.</p>") + js
        self._send(page("Drafts", body))


def tailnet_ip():
    try:
        out = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=10)
        ip = out.stdout.strip().split("\n")[0].strip()
        return ip or None
    except Exception:
        return None


def main():
    global COMPARTMENT, NAME
    ap = argparse.ArgumentParser(description="iPad thin-client voor een compartiment (Tailnet-only).")
    ap.add_argument("naam")
    ap.add_argument("--host", help="Bind-IP (default: Tailnet-IP; gebruik 127.0.0.1 voor test).")
    ap.add_argument("--port", type=int, default=8766)
    args = ap.parse_args()

    if not re.match(r"^[A-Za-z0-9_-]+$", args.naam):
        sys.exit("ongeldige naam")
    COMPARTMENT = CONFIDENTIAL_ROOT / args.naam
    NAME = args.naam
    if not COMPARTMENT.is_dir():
        sys.exit(f"compartiment bestaat niet: {COMPARTMENT}")

    host = args.host or tailnet_ip()
    if not host:
        sys.exit("Tailnet-IP niet gevonden (tailscale actief?). Gebruik --host voor een test.")

    print(f"compartment-serve: http://{host}:{args.port}  (compartiment '{NAME}', Tailnet-only)")
    print("Ctrl-C om te stoppen.")
    with ThreadingHTTPServer((host, args.port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\ngestopt.")


if __name__ == "__main__":
    main()
