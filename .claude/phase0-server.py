#!/usr/bin/env python3
"""
phase0-server.py — Lokale HTTP-server voor Phase 0
===================================================
Serveert statische bestanden uit SERVE_DIR, accepteert POST /skip requests
en genereert on-demand artikel-pagina's voor YouTube-video's via GET /article/{video_id}.

Artikel-generatie verloopt asynchroon: de browser krijgt direct een loading-pagina
terug (met automatische refresh elke 5 seconden) terwijl Ollama in een
achtergrond-thread het artikel genereert. Bij het volgende verzoek wordt het
gecachede artikel geserveerd.

Gebruik (via launchd):
    python3 phase0-server.py
"""

import html
import http.server
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SERVE_DIR        = Path.home() / ".local" / "share" / "phase0-serve"
SCRIPT_DIR       = Path(__file__).parent
TRANSCRIPT_CACHE = SCRIPT_DIR / "transcript_cache"
ARTICLE_CACHE    = SCRIPT_DIR / "article_cache"
SKIP_QUEUE       = SCRIPT_DIR / "skip_queue.jsonl"
PORT             = 8765

OLLAMA_MODEL   = "qwen2.5:7b"
OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 300  # seconden
OLLAMA_NUM_CTX = 32768


class Phase0Handler(http.server.SimpleHTTPRequestHandler):

    # Klasse-brede generatiestatus: video_id -> "pending" | "error:<msg>"
    _generating: dict[str, str] = {}
    _gen_lock = threading.Lock()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(SERVE_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/article/podcast/"):
            path, _, query = self.path.partition("?")
            episode_id = path[len("/article/podcast/"):]
            tag = ""
            for part in query.split("&"):
                if part.startswith("tag="):
                    tag = urllib.parse.unquote(part[4:])
            if re.match(r'^podcast_[0-9a-f]{32}$', episode_id):
                self._serve_podcast_article(episode_id, tag)
            else:
                self._respond_html(400, self._error_page(
                    "Ongeldig aflevering-ID",
                    "Het opgegeven podcast aflevering-ID heeft een onverwacht formaat."
                ))
        elif self.path.startswith("/article/"):
            path, _, query = self.path.partition("?")
            video_id = path[len("/article/"):]
            tag = ""
            for part in query.split("&"):
                if part.startswith("tag="):
                    tag = urllib.parse.unquote(part[4:])
            if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id):
                self._serve_article(video_id, tag)
            else:
                self._respond_html(400, self._error_page(
                    "Ongeldig video-ID",
                    "Het opgegeven YouTube video-ID heeft een onverwacht formaat."
                ))
        elif self.path == "/health":
            try:
                urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                ollama_ok = True
            except Exception:
                ollama_ok = False
            body = json.dumps({"ollama": "ok" if ollama_ok else "unreachable"}).encode()
            self.send_response(200 if ollama_ok else 503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

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

    def _serve_article(self, video_id: str, tag: str = "") -> None:
        """
        Serveert een artikel voor een YouTube-video.
        - Gecached artikel → direct serveren (tag server-side injecteren)
        - Generatie bezig  → loading-pagina (auto-refresh 5s)
        - Fout opgetreden  → foutpagina, staat gecleared
        - Nieuw verzoek    → achtergrond-thread starten, loading-pagina
        """
        ARTICLE_CACHE.mkdir(parents=True, exist_ok=True)
        article_file = ARTICLE_CACHE / f"{video_id}.html"

        # 1. Gecached artikel serveren; COinS-span server-side injecteren met geselecteerde tag
        if article_file.exists():
            content = article_file.read_bytes()
            transcript_file = TRANSCRIPT_CACHE / f"{video_id}.json"
            try:
                data = json.loads(transcript_file.read_text(encoding="utf-8"))
                coins = Phase0Handler._build_coins_span(
                    data.get("title", ""),
                    data.get("channel", ""),
                    data.get("url", f"https://www.youtube.com/watch?v={video_id}"),
                    data.get("published", ""),
                    tag,
                    abstract=data.get("abstract", ""),
                ).encode()
                content = content.replace(b"<!-- COINS_SPAN -->", coins)
            except Exception:
                pass
            self._respond_html(200, content)
            return

        # 2. Controleer generatiestatus
        with Phase0Handler._gen_lock:
            state = Phase0Handler._generating.get(video_id)

        if state == "pending":
            self._respond_html(200, self._loading_page(video_id))
            return

        if state and state.startswith("error:"):
            error_msg = state[6:]
            with Phase0Handler._gen_lock:
                Phase0Handler._generating.pop(video_id, None)
            self._respond_html(500, self._error_page(
                "Fout bij artikelgeneratie", html.escape(error_msg)
            ))
            return

        # 3. Laad transcript
        transcript_file = TRANSCRIPT_CACHE / f"{video_id}.json"
        if not transcript_file.exists():
            self._respond_html(404, self._error_page(
                "Transcript niet gevonden",
                "Dit transcript is nog niet gecached. Voer phase0-score.py opnieuw uit "
                "om transcripten te downloaden voor recente video's."
            ))
            return

        try:
            data = json.loads(transcript_file.read_text(encoding="utf-8"))
        except Exception as e:
            self._respond_html(500, self._error_page("Cache-fout", html.escape(str(e))))
            return

        transcript = data.get("text")
        if not transcript:
            yt_url = data.get("url", f"https://www.youtube.com/watch?v={video_id}")
            self._respond_html(404, self._error_page(
                "Geen transcript beschikbaar",
                f'YouTube heeft geen automatische ondertitels voor deze video. '
                f'<a href="{html.escape(yt_url)}" target="_blank" rel="noopener">'
                f'Bekijk op YouTube &#9654;</a>'
            ))
            return

        # 4. Start generatie in achtergrond-thread
        with Phase0Handler._gen_lock:
            Phase0Handler._generating[video_id] = "pending"

        threading.Thread(
            target=Phase0Handler._generate_in_background,
            args=(video_id, data),
            daemon=True,
        ).start()

        self._respond_html(200, self._loading_page(video_id))

    @staticmethod
    def _generate_in_background(video_id: str, data: dict) -> None:
        """Genereert het artikel in een achtergrond-thread en schrijft het naar de cache."""
        article_file = ARTICLE_CACHE / f"{video_id}.html"
        try:
            article_text = Phase0Handler._call_ollama(
                data.get("text", ""),
                data.get("title", ""),
                data.get("channel", ""),
            )
            article_html = Phase0Handler._build_article_html(
                video_id,
                data.get("title", ""),
                data.get("channel", ""),
                data.get("url", f"https://www.youtube.com/watch?v={video_id}"),
                data.get("published", ""),
                article_text,
            )
            article_file.write_bytes(article_html.encode("utf-8"))
            # Sla volledig artikel op in transcript-cache zodat COinS het als abstract meestuurt
            transcript_file = TRANSCRIPT_CACHE / f"{video_id}.json"
            try:
                cache_data = json.loads(transcript_file.read_text(encoding="utf-8"))
                cache_data["abstract"] = article_text.strip()
                transcript_file.write_text(json.dumps(cache_data, ensure_ascii=False))
            except Exception:
                pass
            # Succes: verwijder uit _generating (gecached bestand is het signaal)
            with Phase0Handler._gen_lock:
                Phase0Handler._generating.pop(video_id, None)
        except urllib.error.URLError as e:
            with Phase0Handler._gen_lock:
                Phase0Handler._generating[video_id] = (
                    f"error:Ollama niet bereikbaar ({e}). "
                    f"Controleer of Ollama actief is en model '{OLLAMA_MODEL}' beschikbaar is."
                )
        except Exception as e:
            with Phase0Handler._gen_lock:
                Phase0Handler._generating[video_id] = f"error:{e}"

    @staticmethod
    def _build_coins_span(title: str, channel: str, yt_url: str, published: str, tag: str = "", rft_type: str = "video", abstract: str = "") -> str:
        """Bouwt een COinS Z3988 span met bibliografische metadata voor Zotero."""
        params = [
            ("ctx_ver", "Z39.88-2004"),
            ("rft_val_fmt", "info:ofi/fmt:kev:mtx:dc"),
            ("rft.title", title),
            ("rft.creator", channel),
            ("rft.identifier", yt_url),
            ("rft.date", published[:4] if published else ""),
            ("rft.type", rft_type),
        ]
        if tag:
            params.append(("rft.subject", tag))
        if abstract:
            params.append(("rft.description", abstract[:3000]))
        coins_title = html.escape(urllib.parse.urlencode(params))
        return f'<span class="Z3988" title="{coins_title}"></span>'

    @staticmethod
    def _call_ollama(transcript: str, title: str, channel: str) -> str:
        """Genereert een leesbaar artikel vanuit een transcript via Ollama."""
        prompt = (
            f'You receive the raw transcript of the YouTube video "{title}" '
            f'from channel "{channel}".\n\n'
            "Write a compact structured summary based on this transcript.\n\n"
            "IMPORTANT: Write in the SAME language as the transcript. Do NOT translate.\n\n"
            "Use exactly this structure:\n\n"
            "## Introduction\n"
            "2-3 sentences describing what the video is about and its main angle.\n\n"
            "## Main Topics\n"
            "A bullet-point list (5-8 bullets) of the key topics, arguments, or findings "
            "discussed in the video. Each bullet is one concise sentence.\n\n"
            "## Conclusion\n"
            "2-3 sentences on the overall takeaway and whether it is relevant for research.\n\n"
            "Do not add information not present in the transcript. "
            "Return only the structured text, no explanations or comments.\n\n"
            f"TRANSCRIPT:\n{transcript[:12000]}"
        )
        payload = json.dumps({
            "model":   OLLAMA_MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"num_ctx": OLLAMA_NUM_CTX},
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            return json.loads(resp.read())["response"]

    def _serve_podcast_article(self, episode_id: str, tag: str = "") -> None:
        """
        Serveert een artikel voor een podcast-aflevering op basis van show notes.
        Zelfde flow als _serve_article: cache → loading → generatie in achtergrond.
        """
        ARTICLE_CACHE.mkdir(parents=True, exist_ok=True)
        article_file = ARTICLE_CACHE / f"{episode_id}.html"

        # 1. Gecached artikel serveren met server-side COinS-injectie
        if article_file.exists():
            content = article_file.read_bytes()
            shownotes_file = TRANSCRIPT_CACHE / f"{episode_id}.json"
            try:
                data = json.loads(shownotes_file.read_text(encoding="utf-8"))
                coins = Phase0Handler._build_coins_span(
                    data.get("title", ""),
                    data.get("channel", ""),
                    data.get("url", ""),
                    data.get("published", ""),
                    tag,
                    rft_type="audio",
                    abstract=data.get("abstract", ""),
                ).encode()
                content = content.replace(b"<!-- COINS_SPAN -->", coins)
            except Exception:
                pass
            self._respond_html(200, content)
            return

        # 2. Controleer generatiestatus
        with Phase0Handler._gen_lock:
            state = Phase0Handler._generating.get(episode_id)

        if state == "pending":
            self._respond_html(200, self._loading_page(episode_id))
            return

        if state and state.startswith("error:"):
            error_msg = state[6:]
            with Phase0Handler._gen_lock:
                Phase0Handler._generating.pop(episode_id, None)
            self._respond_html(500, self._error_page(
                "Fout bij artikelgeneratie", html.escape(error_msg)
            ))
            return

        # 3. Laad show notes uit cache
        shownotes_file = TRANSCRIPT_CACHE / f"{episode_id}.json"
        if not shownotes_file.exists():
            self._respond_html(404, self._error_page(
                "Show notes niet gevonden",
                "De show notes voor deze aflevering zijn nog niet gecached. "
                "Voer phase0-score.py opnieuw uit."
            ))
            return

        try:
            data = json.loads(shownotes_file.read_text(encoding="utf-8"))
        except Exception as e:
            self._respond_html(500, self._error_page("Cache-fout", html.escape(str(e))))
            return

        shownotes_text = data.get("text", "")
        if not shownotes_text:
            self._respond_html(404, self._error_page(
                "Geen show notes beschikbaar",
                "Deze aflevering heeft geen show notes om een artikel van te genereren."
            ))
            return

        # 4. Start generatie in achtergrond-thread
        with Phase0Handler._gen_lock:
            Phase0Handler._generating[episode_id] = "pending"

        threading.Thread(
            target=Phase0Handler._generate_podcast_in_background,
            args=(episode_id, data),
            daemon=True,
        ).start()

        self._respond_html(200, self._loading_page(episode_id))

    @staticmethod
    def _generate_podcast_in_background(episode_id: str, data: dict) -> None:
        """Genereert het podcast-artikel in een achtergrond-thread en schrijft het naar de cache."""
        article_file = ARTICLE_CACHE / f"{episode_id}.html"
        try:
            article_text = Phase0Handler._call_ollama_shownotes(
                data.get("text", ""),
                data.get("title", ""),
                data.get("channel", ""),
            )
            article_html = Phase0Handler._build_podcast_article_html(
                episode_id,
                data.get("title", ""),
                data.get("channel", ""),
                data.get("url", ""),
                data.get("published", ""),
                article_text,
            )
            article_file.write_bytes(article_html.encode("utf-8"))
            # Sla volledig artikel op in shownotes-cache zodat COinS het als abstract meestuurt
            shownotes_file = TRANSCRIPT_CACHE / f"{episode_id}.json"
            try:
                cache_data = json.loads(shownotes_file.read_text(encoding="utf-8"))
                cache_data["abstract"] = article_text.strip()
                shownotes_file.write_text(json.dumps(cache_data, ensure_ascii=False))
            except Exception:
                pass
            with Phase0Handler._gen_lock:
                Phase0Handler._generating.pop(episode_id, None)
        except urllib.error.URLError as e:
            with Phase0Handler._gen_lock:
                Phase0Handler._generating[episode_id] = (
                    f"error:Ollama niet bereikbaar ({e}). "
                    f"Controleer of Ollama actief is en model '{OLLAMA_MODEL}' beschikbaar is."
                )
        except Exception as e:
            with Phase0Handler._gen_lock:
                Phase0Handler._generating[episode_id] = f"error:{e}"

    @staticmethod
    def _call_ollama_shownotes(shownotes: str, title: str, channel: str) -> str:
        """Genereert een leesbaar artikel vanuit podcast show notes via Ollama."""
        prompt = (
            f'You receive the show notes of the podcast episode "{title}" '
            f'from "{channel}".\n\n'
            "Write a compact structured summary based on these show notes.\n\n"
            "IMPORTANT: Write in the SAME language as the show notes. Do NOT translate.\n\n"
            "Use exactly this structure:\n\n"
            "## Introduction\n"
            "2-3 sentences describing what the episode is about and its main angle.\n\n"
            "## Main Topics\n"
            "A bullet-point list (5-8 bullets) of the key topics, arguments, or findings "
            "discussed. Each bullet is one concise sentence.\n\n"
            "## Conclusion\n"
            "2-3 sentences on the overall takeaway and whether it is relevant for research.\n\n"
            "Do not add information not present in the show notes. "
            "Return only the structured text, no explanations or comments.\n\n"
            f"SHOW NOTES:\n{shownotes[:6000]}"
        )
        payload = json.dumps({
            "model":   OLLAMA_MODEL,
            "prompt":  prompt,
            "stream":  False,
            "options": {"num_ctx": OLLAMA_NUM_CTX},
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT) as resp:
            return json.loads(resp.read())["response"]

    @staticmethod
    def _build_podcast_article_html(
        episode_id: str, title: str, channel: str,
        episode_url: str, published: str, article_text: str,
    ) -> str:
        """Bouwt een volledige HTML-pagina van het gegenereerde podcast-artikel."""
        pub_display = ""
        if published:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                pub_display = dt.strftime("%-d %b %Y")
            except Exception:
                pub_display = published[:10]

        article_body = Phase0Handler._simple_md_to_html(article_text)
        t     = html.escape(title)
        ch    = html.escape(channel)
        url   = html.escape(episode_url)
        pub   = html.escape(published[:10] if published else "")
        pub_d = html.escape(pub_display)

        return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="author" content="{ch}">
<meta name="date" content="{pub}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{t}">
<meta property="og:url" content="{url}">
<meta name="citation_title" content="{t}">
<meta name="citation_author" content="{ch}">
<meta name="citation_date" content="{pub}">
<!-- COINS_SPAN -->
<style>
  body {{ max-width: 720px; margin: 2rem auto; padding: 0 1.25rem;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 16px; line-height: 1.7; color: #1a1a1a; background: #f9f9f7; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1c1c1e; color: #f2f2f7; }}
    a {{ color: #5ac8fa; }}
    header, footer {{ border-color: #3a3a3c; }}
  }}
  header {{ border-bottom: 1px solid #e0e0da; padding-bottom: 1rem; margin-bottom: 1.5rem; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .5rem; line-height: 1.3; }}
  .meta {{ font-size: .85rem; color: #6b6b6b; }}
  .tag-bar {{
    display: flex; gap: .5rem; align-items: center; margin-top: .75rem; flex-wrap: wrap;
  }}
  .tag-bar span {{ font-size: .8rem; color: #6b6b6b; }}
  .tag-btn {{
    border: 1px solid #d0d0cc; border-radius: 6px; background: none;
    padding: .3rem .65rem; font-size: .85rem; cursor: pointer;
    color: #1a1a1a; transition: background .1s, border-color .1s;
  }}
  .tag-btn:hover {{ background: #f0f0ec; }}
  .tag-btn.selected {{ background: #1a1a1a; color: #fff; border-color: #1a1a1a; }}
  @media (prefers-color-scheme: dark) {{
    .tag-btn {{ color: #f2f2f7; border-color: #48484a; }}
    .tag-btn:hover {{ background: #3a3a3c; }}
    .tag-btn.selected {{ background: #f2f2f7; color: #1a1a1a; border-color: #f2f2f7; }}
  }}
  h2 {{ font-size: 1.1rem; margin: 1.75rem 0 .4rem; }}
  h3 {{ font-size: 1rem; font-weight: 600; margin: 1.25rem 0 .3rem; }}
  p {{ margin: 0 0 .85rem; }}
  footer {{ margin-top: 2.5rem; font-size: .8rem; color: #999;
            border-top: 1px solid #e0e0da; padding-top: .75rem; }}
</style>
</head>
<body>
<header>
  <h1>{t}</h1>
  <div class="meta">
    {ch}{(" &nbsp;&middot;&nbsp; " + pub_d) if pub_d else ""}
    {('&nbsp;&middot;&nbsp; <a href="' + url + '" target="_blank" rel="noopener">&#127911; luisteren</a>') if url else ""}
  </div>
  <div class="tag-bar">
    <span>Tag voor Zotero:</span>
    <a href="?tag=%E2%9C%85" class="tag-btn" data-tag="✅">✅ verwerken</a>
    <a href="?tag=%F0%9F%93%96" class="tag-btn" data-tag="📖">📖 later lezen</a>
    <a href="?" class="tag-btn" data-tag="">geen tag</a>
  </div>
</header>
<script>
(function() {{
  const tag = decodeURIComponent(new URLSearchParams(window.location.search).get("tag") || "");
  document.querySelectorAll(".tag-btn[data-tag]").forEach(btn => {{
    if (btn.dataset.tag === tag) btn.classList.add("selected");
  }});
}})();
</script>
<main>
{article_body}
</main>
<footer>
  Gegenereerd door Phase 0 via {html.escape(OLLAMA_MODEL)} op basis van show notes
  {('&nbsp;&middot;&nbsp; <a href="' + url + '" target="_blank" rel="noopener">originele aflevering</a>') if url else ""}
  &nbsp;&middot;&nbsp; <a href="/">&#8592; Phase 0 RSS</a>
</footer>
</body>
</html>"""

    @staticmethod
    def _loading_page(video_id: str) -> bytes:
        """Geeft een loading-pagina terug die elke 5 seconden automatisch herlaadt."""
        return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="5">
<title>Artikel genereren\u2026</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 480px; margin: 5rem auto; padding: 0 1.5rem; text-align: center;
         background: #f9f9f7; color: #1a1a1a; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1c1c1e; color: #f2f2f7; }}
    a {{ color: #5ac8fa; }}
  }}
  .icon {{ font-size: 2.5rem; animation: spin 2s linear infinite; display: inline-block; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  h2 {{ margin: 1rem 0 .5rem; font-size: 1.2rem; }}
  p {{ color: #6b6b6b; font-size: .9rem; line-height: 1.6; margin: .4rem 0; }}
</style>
</head>
<body>
  <div class="icon">&#9881;&#65039;</div>
  <h2>Artikel genereren\u2026</h2>
  <p>Ollama ({OLLAMA_MODEL}) verwerkt het transcript.</p>
  <p>Typisch een halve minuut maximaal. Deze pagina ververst automatisch elke 5 seconden.</p>
  <p style="margin-top:1.5rem"><a href="/">&#8592; Terug naar Phase 0</a></p>
</body>
</html>""".encode("utf-8")

    @staticmethod
    def _build_article_html(
        video_id: str, title: str, channel: str,
        yt_url: str, published: str, article_text: str,
    ) -> str:
        """Bouwt een volledige HTML-pagina van het gegenereerde artikel."""
        pub_display = ""
        if published:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                pub_display = dt.strftime("%-d %b %Y")
            except Exception:
                pub_display = published[:10]

        article_body = Phase0Handler._simple_md_to_html(article_text)
        t     = html.escape(title)
        ch    = html.escape(channel)
        url   = html.escape(yt_url)
        pub   = html.escape(published[:10] if published else "")
        pub_d = html.escape(pub_display)

        return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="author" content="{ch}">
<meta name="date" content="{pub}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{t}">
<meta property="og:url" content="{url}">
<meta name="citation_title" content="{t}">
<meta name="citation_author" content="{ch}">
<meta name="citation_date" content="{pub}">
<!-- COINS_SPAN -->
<style>
  body {{ max-width: 720px; margin: 2rem auto; padding: 0 1.25rem;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 16px; line-height: 1.7; color: #1a1a1a; background: #f9f9f7; }}
  @media (prefers-color-scheme: dark) {{
    body {{ background: #1c1c1e; color: #f2f2f7; }}
    a {{ color: #5ac8fa; }}
    header, footer {{ border-color: #3a3a3c; }}
  }}
  header {{ border-bottom: 1px solid #e0e0da; padding-bottom: 1rem; margin-bottom: 1.5rem; }}
  h1 {{ font-size: 1.35rem; margin: 0 0 .5rem; line-height: 1.3; }}
  .meta {{ font-size: .85rem; color: #6b6b6b; }}
  .tag-bar {{
    display: flex; gap: .5rem; align-items: center; margin-top: .75rem; flex-wrap: wrap;
  }}
  .tag-bar span {{ font-size: .8rem; color: #6b6b6b; }}
  .tag-btn {{
    border: 1px solid #d0d0cc; border-radius: 6px; background: none;
    padding: .3rem .65rem; font-size: .85rem; cursor: pointer;
    color: #1a1a1a; transition: background .1s, border-color .1s;
  }}
  .tag-btn:hover {{ background: #f0f0ec; }}
  .tag-btn.selected {{ background: #1a1a1a; color: #fff; border-color: #1a1a1a; }}
  @media (prefers-color-scheme: dark) {{
    .tag-btn {{ color: #f2f2f7; border-color: #48484a; }}
    .tag-btn:hover {{ background: #3a3a3c; }}
    .tag-btn.selected {{ background: #f2f2f7; color: #1a1a1a; border-color: #f2f2f7; }}
  }}
  h2 {{ font-size: 1.1rem; margin: 1.75rem 0 .4rem; }}
  h3 {{ font-size: 1rem; font-weight: 600; margin: 1.25rem 0 .3rem; }}
  p {{ margin: 0 0 .85rem; }}
  footer {{ margin-top: 2.5rem; font-size: .8rem; color: #999;
            border-top: 1px solid #e0e0da; padding-top: .75rem; }}
</style>
</head>
<body>
<header>
  <h1>{t}</h1>
  <div class="meta">
    {ch}{(" &nbsp;&middot;&nbsp; " + pub_d) if pub_d else ""}
    &nbsp;&middot;&nbsp; <a href="{url}" target="_blank" rel="noopener">&#9654; bekijk op YouTube</a>
  </div>
  <div class="tag-bar">
    <span>Tag voor Zotero:</span>
    <a href="?tag=%E2%9C%85" class="tag-btn" data-tag="✅">✅ verwerken</a>
    <a href="?tag=%F0%9F%93%96" class="tag-btn" data-tag="📖">📖 later lezen</a>
    <a href="?" class="tag-btn" data-tag="">geen tag</a>
  </div>
</header>
<script>
(function() {{
  const tag = decodeURIComponent(new URLSearchParams(window.location.search).get("tag") || "");
  document.querySelectorAll(".tag-btn[data-tag]").forEach(btn => {{
    if (btn.dataset.tag === tag) btn.classList.add("selected");
  }});
}})();
</script>
<main>
{article_body}
</main>
<footer>
  Gegenereerd door Phase 0 via {html.escape(OLLAMA_MODEL)}
  &nbsp;&middot;&nbsp; <a href="{url}" target="_blank" rel="noopener">originele video op YouTube</a>
  &nbsp;&middot;&nbsp; <a href="/">&#8592; Phase 0 RSS</a>
</footer>
</body>
</html>"""

    @staticmethod
    def _simple_md_to_html(text: str) -> str:
        """Converteert eenvoudige Markdown naar HTML (h2, h3, p)."""
        result = []
        for line in text.split("\n"):
            s = line.strip()
            if s.startswith("### "):
                result.append(f"<h3>{html.escape(s[4:])}</h3>")
            elif s.startswith("## "):
                result.append(f"<h2>{html.escape(s[3:])}</h2>")
            elif s.startswith("# "):
                result.append(f"<h2>{html.escape(s[2:])}</h2>")
            elif s:
                result.append(f"<p>{html.escape(s)}</p>")
        return "\n".join(result)

    @staticmethod
    def _error_page(heading: str, body_html: str) -> bytes:
        """Genereert een eenvoudige HTML-foutpagina."""
        return f"""<!DOCTYPE html>
<html lang="nl"><head><meta charset="utf-8">
<title>{html.escape(heading)}</title>
<style>body{{font-family:sans-serif;max-width:600px;margin:2rem auto;padding:0 1rem}}</style>
</head><body>
<h2>{html.escape(heading)}</h2>
<p>{body_html}</p>
<p><a href="/">&#8592; Terug naar Phase 0</a></p>
</body></html>""".encode("utf-8")

    def _respond(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _respond_html(self, code: int, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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
            or str(args[0]).startswith("GET /article/")
            or (len(args) > 1 and str(args[1]) >= "400")
        ):
            super().log_message(format, *args)


if __name__ == "__main__":
    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    ARTICLE_CACHE.mkdir(parents=True, exist_ok=True)
    print(f"phase0-server: luistert op http://localhost:{PORT}")
    print(f"Skip-queue:    {SKIP_QUEUE}")
    print(f"Artikel-cache: {ARTICLE_CACHE}")
    with http.server.ThreadingHTTPServer(("", PORT), Phase0Handler) as httpd:
        httpd.serve_forever()
