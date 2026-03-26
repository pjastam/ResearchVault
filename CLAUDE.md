# CLAUDE.md — Werkwijze ResearchVault

## Obsidian-conventies
- Alle bestanden zijn Markdown (.md)
- Gebruik [[dubbele haken]] voor interne links tussen notes
- Gebruik #tags voor thematische categorisatie
- Bestandsnamen: gebruik koppeltekens, geen spaties (bijv. `auteur-2024-titel.md`)

## Vault-structuur
- `literature/` — één note per paper of bron uit Zotero
- `syntheses/` — thematische syntheses van meerdere bronnen
- `projects/` — projectspecifieke documentatie
- `daily/` — dagelijkse notities en logboek
- `inbox/` — ruwe input die nog verwerkt moet worden

## Literatuurnotities (uit Zotero)

Elke literatuurnotitie begint met de volgende YAML frontmatter:
```yaml
---
title: "Volledige titel van het werk"
authors: ["Achternaam, Voornaam", ...]
year: JJJJ
journal: "Naam tijdschrift of uitgever"
citation_key: auteur2024kernwoord
zotero: "zotero://select/library/1/items/ITEMKEY"
tags: [thema1, thema2]
status: unread
---
```

`status` geeft aan of het artikel al gelezen is: `unread` (standaard) of `read`. Uitzondering: als het Zotero-item de tag `✅` had, gebruik dan `status: read`.

**Let op:** schrijf tags zónder `#` in de frontmatter (bijv. `[beleid, zorg]`). Obsidian voegt de `#` automatisch toe in de UI. Een `#` binnen een YAML-array breekt de frontmatter-parse.

Vervang `ITEMKEY` door de werkelijke Zotero item key, op te halen via Zotero MCP:
`zotero-mcp get-item-key <titel of DOI>` of via het `key`-veld in de MCP-respons.

Na de frontmatter bevat elke notitie:

* Kernvraag en hoofdargument
* Kernbevindingen (3–5 punten)
* Methodologische notities
* Citaten die relevant zijn voor mijn onderzoek (in de originele taal)
* Links naar gerelateerde notities in de vault ([[dubbele haken]])

## Taal
- Antwoord in het Nederlands tenzij anders gevraagd
- Schrijf literatuurnotities in het Nederlands, citaten in de originele taal

## Zotero-workflow
- Gebruik Zotero MCP om papers op te halen via hun titel of sleutelwoorden
- Sla literatuurnotities op als `literature/[auteur-jaar-kernwoord].md`
- Voeg altijd een #tag toe voor het thema van de paper

## _inbox prioritering (index-score.py)
- Gebruik `.claude/index-score.py` om items in de Zotero `_inbox` te scoren op relevantie vóór de fase 2-review
- Het script vergelijkt de embeddings van inbox-items met het gewogen gemiddelde van je bestaande bibliotheek (via ChromaDB, model: all-MiniLM-L6-v2)
- Items met PDF-annotaties in Zotero wegen zwaarder mee in het voorkeursprofiel (gewicht 3 vs. 1)
- Uitvoeren: `~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py`
- Output: gesorteerde lijst met scores 0–100, labels 🟢 (≥70) · 🟡 (40–69) · 🔴 (<40)

## YouTube-transcripten (yt-dlp)
- Transcripten worden opgeslagen in `inbox/` als `.vtt`-bestanden
- Verwerk een transcript naar een note in `literature/` met de volgende structuur:
  - Titel, spreker, kanaal, datum, URL
  - Samenvatting (3–5 zinnen)
  - Kernpunten met tijdcodes
  - Relevante citaten (met tijdcode)
  - Links naar gerelateerde notes in de vault
- Bestandsnaam voor transcript-notes: `[spreker-jaar-kernwoord].md` met #tag `#video`
- Ruwe `.vtt`-bestanden verwijder je uit `inbox/` nadat de note is aangemaakt

## Zotero database-onderhoud
- De semantische zoekdatabase moet periodiek worden bijgewerkt na het toevoegen van nieuwe papers
- Herinner de gebruiker eraan de database bij te werken als er meer dan een week verstreken is sinds de laatste update, of als zoekopdrachten recente toevoegingen missen
- Gebruik het commando `update-zotero` (alias) of `zotero-mcp update-db --fulltext` voor een volledige update
- Check de status met `zotero-status` of `zotero-mcp db-status`

## Podcast-transcripten (whisper.cpp + yt-dlp)
- Audio wordt gedownload via yt-dlp en opgeslagen in `inbox/` als `.mp3`
- Transcriptie verloopt lokaal via whisper.cpp (volledig offline)
- Whisper detecteert de taal automatisch; geef `--language` alleen expliciet mee als de automatische detectie onjuist is
- Verwerk een transcript naar een note in `literature/` met de volgende structuur:
  - Titel, spreker(s), programma/kanaal, datum, URL of bronvermelding
  - Samenvatting (3–5 zinnen)
  - Kernpunten met tijdcodes
  - Relevante uitspraken (met tijdcode, in de originele taal)
  - Links naar gerelateerde notes in de vault
- Bestandsnaam voor podcast-notes: `[spreker-jaar-kernwoord].md` met #tag `#podcast`
- Bij lange podcasts (> 45 min): maak eerst een gelaagde samenvatting (hoofdlijn → per segment)
- Ruwe `.mp3` en `.txt`-bestanden verwijder je uit `inbox/` nadat de note is aangemaakt

## Phase 0 — RSS-filtering (phase0-score.py)

Phase 0 filtert RSS-feeds automatisch op relevantie vóórdat je ze handmatig doorscant. Het draait dagelijks via launchd en produceert een gefilterde feed en HTML-pagina.

**Bestanden:**
- `.claude/phase0-feeds.txt` — lijst van feed-URLs (één per regel, `#` = commentaar); bevat webartikel-, YouTube- en podcast-feeds ingedeeld per categorie met `# ── Naam ────` headers
- `.claude/phase0-score.py` — haalt feeds op, scoort items, detecteert brontype; voor YouTube-items haalt het eerst een transcript op via `youtube_transcript_api` (gecachet in `transcript_cache/`) en gebruikt de transcripttekst voor de scoreberekening; schrijft `filtered.xml` en `filtered.html`
- `.claude/phase0_core.py` — gedeelde functies: `cosine_similarity`, `compute_weighted_profile`, `score_label`, `detect_source_type`; constanten: `THRESHOLD_GREEN`, `THRESHOLD_YELLOW`, `WEIGHT_DEFAULT`, `WEIGHT_ANNOTATIONS`
- `.claude/phase0-server.py` — lokale HTTP-server (poort 8765); handelt `POST /skip` af en serveert `GET /article/{video_id}`: genereert een leesbaar artikel via Ollama `qwen2.5:7b` (asynchroon, met laadpagina die elke 5 seconden herlaadt); resultaten gecachet in `article_cache/`
- `.claude/phase0-learn.py` — leerloop: verwerkt skip-queue, matcht Zotero-toevoegingen, geeft drempeladvies
- `.claude/score_log.jsonl` — groeiend logboek (URL, score, bron, source_type, timestamp, added_to_zotero, skipped)
- `.claude/skip_queue.jsonl` — wachtrij van expliciet afgewezen items (👎); dagelijks verwerkt door phase0-learn.py
- `.claude/transcript_cache/` — JSON-cache van YouTube-transcripten (per video_id); aangemaakt door phase0-score.py
- `.claude/article_cache/` — HTML-cache van gegenereerde artikelen (per video_id); aangemaakt door phase0-server.py
- `~/.local/share/phase0-serve/` — serveermap (buiten Documents vanwege macOS TCC)

**URLs (lokale HTTP-server op poort 8765):**
- `http://localhost:8765/filtered.html` — HTML-lezer met score- en bronweergave + type-filterknoppen **Alles / 📄 / ▶️ / 🎙️** (Mac/iPhone/iPad)
- `http://localhost:8765/filtered.xml` — Atom-feed voor NetNewsWire
- `http://localhost:8765/article/{video_id}` — gegenereerd leesartikel voor een YouTube-video (structuur: Inleiding · Kernpunten · Conclusie; taal = originele videotaal)

**YouTube-artikelen:** klikken op een YouTube-headline in de HTML-lezer opent een gegenereerd artikel in plaats van de YouTube-pagina. Het artikel bevat knoppen om een Zotero-tag mee te geven vóór opslaan via de Zotero Connector: **✅ verwerken** · **📖 later lezen** · **geen tag** (standaard). De tag wordt meegegeven via een COinS-span (`<span class="Z3988">`) zodat de Zotero Connector hem automatisch overneemt. Model: `qwen2.5:7b` (Phase 0 only); voor Phase 2+ wordt `qwen3.5:9b` gebruikt.

**Scores en labels:** 🟢 ≥50 · 🟡 40–49 · 🔴 <40 (drempels worden bijgesteld via phase0-learn.py)

**Handmatig uitvoeren:**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/phase0-score.py
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/phase0-learn.py
```

**👎-knop:** elk item in de HTML-lezer heeft een 👎-knop. Klikken markeert het item als `skipped: true` in het logboek (via de server) en visueel als doorgestreept. Dit is een sterk expliciet negatief signaal, onderscheiden van "niet aangeklikt" (ambigu). Klikken op de headline markeert het item als gelezen en opent het artikel.

**Leerloop:** phase0-learn.py verwerkt eerst de skip-queue (👎-signalen), matcht daarna recent aan Zotero toegevoegde items aan het logboek, en onderscheidt drie categorieën: ✅ positieven · 👎 expliciet afgewezen · ❌ zwak negatief (niet toegevoegd na timeout). Na ≥30 positieven geeft het een drempeladvies. Pas dan `THRESHOLD_GREEN` en `THRESHOLD_YELLOW` in `phase0-score.py` aan.

**launchd-agents** (laden bij inloggen):
- `nl.researchvault.phase0-server` — HTTP-server permanent actief
- `nl.researchvault.phase0-score` — score-run dagelijks om 06:00
- `nl.researchvault.phase0-learn` — leerloop dagelijks om 06:15

## RSS-feeds
- RSS-feeds worden gefilterd via Phase 0; de HTML-lezer (`http://localhost:8765/filtered.html`) of de Atom-feed in NetNewsWire toont items gesorteerd op relevantiescore
- Feeds toevoegen: zet de feed-URL op een nieuwe regel in `.claude/phase0-feeds.txt`
- Academische artikelen die interessant zijn: voeg ze toe aan Zotero via de browser-extensie of iOS-app → komen in `_inbox` terecht
- Niet-academische artikelen: voeg toe via Zotero Connector, of geef de URL door met `inbox [URL]` voor directe opslag als Markdown in `inbox/`
- Bestandsnaam voor RSS-items zonder Zotero-record: `[bron-jaar-kernwoord].md` met #tag `#web` of `#beleid`

## Spaced repetition (Obsidian plugin)
- Flashcards worden aangemaakt na elke literatuurnotitie of synthese
- Formaat: vraag en antwoord gescheiden door `?` op een nieuwe regel, omsloten door `#flashcard`-tag
- Maak maximaal 5 kaarten per bron — kies de meest relevante concepten
- Dagelijkse review via Obsidian Spaced Repetition plugin (zijbalk → Kaarten beoordelen)

## Actieve skills
- Lees en volg `.claude/skills/research-workflow-skill-v1.14.md` bij elke research-sessie.