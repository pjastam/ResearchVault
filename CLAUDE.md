# CLAUDE.md — Werkwijze ResearchVault

> **Bevroren specificatie.** Pas dit bestand alleen aan na expliciete beslissing. Elke wijziging verandert het gedrag van alle toekomstige ingests en lint-runs.

## Obsidian-conventies
- Alle bestanden zijn Markdown (.md)
- Gebruik [[dubbele haken]] voor interne links tussen notes
- Gebruik #tags voor thematische categorisatie
- Bestandsnamen: gebruik koppeltekens, geen spaties (bijv. `auteur-2024-kernwoord1-kernwoord2.md`)
  - Na het jaar: 2–4 zelfstandige naamwoorden gekozen door Qwen op basis van titel en TLDR
  - `process_item.py` genereert de bestandsnaam automatisch — niet handmatig opgeven

## Vault-structuur

| Map | Paginatype | Inhoud |
| --- | --- | --- |
| `literature/` | Source notes | Één note per paper of bron uit Zotero |
| `syntheses/` | Syntheses | Thematische syntheses van meerdere bronnen |
| `concepts/` | Concepts | Methodologische concepten (averechtse selectie, moral hazard, risicoverevening, etc.) |
| `authors/` | Authors | Onderzoekerprofielen met publicatiehistorie en relevantie |
| `debates/` | Debates | Lopende wetenschappelijke discussies en tegenstellingen tussen studies |
| `projects/` | Projects | Projectspecifieke documentatie en Talma-koppelingen |
| `daily/` | — | Dagelijkse notities en logboek |
| `inbox/` | — | Ruwe input die nog verwerkt moet worden |
| `meta/candidates/` | — | Staging area: Qwen-drafts vóór promotie naar `literature/` (zie Ingest-procedure) |

## Literatuurnotities (uit Zotero)

Elke literatuurnotitie begint met de volgende YAML frontmatter:
```yaml
---
title: "Volledige titel van het werk"
authors: ["Achternaam, Voornaam", ...]
year: JJJJ
journal: "Naam tijdschrift of uitgever"
citation_key: auteur2024kernwoord
zotero: "zotero://select/library/items/ITEMKEY"
tags: [thema1, thema2]
status: unread
---
```

`status` geeft aan of het artikel al gelezen is: `unread` (standaard) of `read`. Uitzondering: als het Zotero-item de tag `✅` had, gebruik dan `status: read`.

**Let op:** schrijf tags zónder `#` in de frontmatter (bijv. `[beleid, zorg]`). Obsidian voegt de `#` automatisch toe in de UI. Een `#` binnen een YAML-array breekt de frontmatter-parse.

Vervang `ITEMKEY` door de werkelijke Zotero item key, op te halen via Zotero MCP:
`zotero-mcp get-item-key <titel of DOI>` of via het `key`-veld in de MCP-respons.

Na de frontmatter bevat elke notitie:

* **TLDR** — kernvraag en hoofdargument in 2–3 zinnen (wordt gebruikt door de LLM om te beslissen of de volledige notitie gelezen moet worden)
* Kernbevindingen (3–5 punten)
* Methodologische notities
* Citaten die relevant zijn voor mijn onderzoek (in de originele taal) — **alleen voor papers en webartikelen**; weggelaten voor video/podcast (timestamps onbetrouwbaar)
* Links naar gerelateerde notities in de vault ([[dubbele haken]])

**Cross-link drempelwaarden:** voeg een `[[link]]` toe als een notitie minstens twee gedeelde kernbegrippen heeft met de doelnotitie, of als er een directe citatie-relatie bestaat. Voeg geen links toe op basis van oppervlakkige overeenkomst in thema alleen.

## Taal
- Antwoord in het Nederlands tenzij anders gevraagd
- Schrijf literatuurnotities in de taal van de originele bron (Engels artikel → Engelstalige note, Nederlands artikel → Nederlandstalige note)
- Citaten altijd in de originele taal

## Zotero-workflow
- Gebruik Zotero MCP om papers op te halen via hun titel of sleutelwoorden
- Sla literatuurnotities op als `literature/[auteur-jaar-kernwoord].md`
- Voeg altijd een #tag toe voor het thema van de paper

## Ingest-procedure

De LLM compileert bestaande kennis — hij genereert geen nieuwe kennis. Prompts voor Qwen zijn kort en structureel.

**Stap 1 — Kwaliteitscheck (Qwen)**
Beoordeel of het item de vault waard is via `index-score.py`. Items met score < 40 (🔴) worden niet ingested tenzij er een expliciete reden is.

**Stap 2 — Kandidaat aanmaken (Qwen via `process_item.py`)**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/process_item.py \
  --item-key ITEMKEY --output-dir meta/candidates/ [overige vlaggen]
```
De draft verschijnt in `meta/candidates/[auteur-jaar-kw].md`. Geen bron-inhoud bereikt Claude Code.

**Stap 3 — Human review**
Lees de kandidaat-notitie. Geef Go of No-go. Bij No-go: verwijder het bestand uit `meta/candidates/`.

**Stap 4 — Promotie naar `literature/` (bij Go)**
```bash
mv meta/candidates/[bestand].md literature/[bestand].md
```

**Stap 5 — Cross-links toevoegen (hyalo + Qwen)**
Zoek verwante notities:
```bash
hyalo find "[kernbegrip]" --glob "literature/*.md" --format text
```
Voeg `[[links]]` toe aan de nieuwe notitie én aan de 2–5 meest verwante bestaande notities (alleen bij drempelwaarde — zie Literatuurnotities).

**Stap 6 — Syntheses bijwerken (Qwen)**
Controleer welke syntheses relevant zijn en voeg een bullet of sectie toe.

**Ollama-routing:**
- Kwaliteitscheck, tekstgeneratie, cross-link-suggesties, synthese-aanvullingen → Qwen (lokaal)
- Coördinatie, beslissingen, review → Claude (orchestrator)
- Navigatie, zoeken, link management → hyalo (geen LLM)

## _inbox prioritering (index-score.py)
- Gebruik `.claude/index-score.py` om items in de Zotero `_inbox` te scoren op relevantie vóór de fase 2-review
- Het script vergelijkt de embeddings van inbox-items met het gewogen gemiddelde van je bestaande bibliotheek (via ChromaDB, model: all-MiniLM-L6-v2)
- Items met PDF-annotaties in Zotero wegen zwaarder mee in het voorkeursprofiel (gewicht 3 vs. 1)
- Uitvoeren: `~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py`
- Output: gesorteerde lijst met scores 0–100, labels 🟢 (≥70) · 🟡 (40–69) · 🔴 (<40)

## Zotero-hulpscripts
- `.claude/zotero-inbox.py` — voegt een item toe aan de Zotero `_inbox` collectie via de web API; wordt intern aangeroepen door de feedreader-server bij ✅/📖 acties vanuit de HTML-lezer of NetNewsWire
- `.claude/zotero-remove-from-inbox.py` — verwijdert een item uit de `_inbox` na verwerking:
  ```bash
  ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
  ```
- `.claude/zotero_utils.py` — gedeelde hulpfuncties voor beide scripts (API-sleutel uitlezen uit `~/.zprofile`, collectie-ID opzoeken)

## YouTube-transcripten (attach-transcript.py)

YouTube-items volgen een eager transcript-pipeline: bij ✅ in de feedreader wordt het transcript meteen opgehaald en als bijlage in Zotero opgeslagen, zodat de Go/No-go op inhoud kan worden gebaseerd.

**Transcript-bijlage aanmaken (voor Go/No-go):**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py ITEMKEY
```
Dit doet:
1. Transcript ophalen via `YouTubeTranscriptApi` (of uit `transcript_cache/`)
2. Qwen genereert een cleaned versie + abstract (3–5 zinnen)
3. Cleaned transcript als `.txt`-bijlage naar Zotero; abstract als `abstractNote`

**Na Go: literatuurnotitie aanmaken via `process_item.py`** — zelfde als papers (zie Ingest-procedure).

**Notitiestructuur voor video/podcast:**
- Geen `## Relevant quotes`-sectie — tijdcodes zijn onbetrouwbaar zonder geverifieerde bron
- Overige secties zoals papers: TLDR, Key findings, Methodological notes, Related notes, Flashcards

**Fallback:** `fetch-fulltext.py` leest de transcript-bijlage uit het Zotero-item (lokale API); yt-dlp is niet meer nodig voor de pipeline.

## Zotero database-onderhoud
- De semantische zoekdatabase wordt automatisch bijgewerkt dagelijks om 06:00 via de nachtelijke-taken daemon (`nl.pietstam.nachtelijke-taken`) — geen handmatige actie nodig vóór een sessie
- Herinner de gebruiker eraan de database handmatig bij te werken als zoekopdrachten recente toevoegingen missen die van dezelfde dag zijn (de automatische update draait om 06:00)
- Gebruik het commando `update-zotero` (alias) of `zotero-mcp update-db --fulltext` voor een handmatige volledige update
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

## Feedreader — RSS-filtering (feedreader-score.py)

De feedreader scoort RSS/YouTube/podcast-feeds automatisch op relevantie en produceert een gefilterde HTML-lezer en Atom-feed. Het is de automatische filterfunctie binnen fase 1 van de workflow. Draait dagelijks via launchd.

**Bestanden:**
- `.claude/feedreader-list.txt` — lijst van feed-URLs (één per regel, `#` = commentaar); bevat webartikel-, YouTube- en podcast-feeds ingedeeld per categorie met `# ── Naam ────` headers
- `.claude/feedreader-score.py` — haalt feeds op, scoort items, detecteert brontype; voor YouTube-items haalt het eerst een transcript op via `youtube_transcript_api` (gecachet in `transcript_cache/`) en gebruikt de transcripttekst voor de scoreberekening; voor podcast-items met show notes ≥ 200 tekens (constante `SHOWNOTES_MIN_LENGTH`) worden de show notes gecachet in `transcript_cache/podcast_{episode_id}.json` (`episode_id` = `podcast_` + MD5-hash van de URL); schrijft `filtered.xml` en `filtered.html`
- `.claude/feedreader_core.py` — gedeelde functies: `cosine_similarity`, `compute_weighted_profile`, `score_label`, `detect_source_type`; constanten: `THRESHOLD_GREEN`, `THRESHOLD_YELLOW`, `WEIGHT_DEFAULT`, `WEIGHT_ANNOTATIONS`
- `.claude/feedreader-server.py` — lokale HTTP-server (poort 8765); handelt `POST /skip` af en serveert `GET /article/{video_id}` (YouTube) en `GET /article/podcast/{episode_id}` (podcast): genereert een leesbaar artikel via Ollama `qwen2.5:7b` (asynchroon, met laadpagina die elke 5 seconden herlaadt); na generatie wordt het volledige artikel ook als `abstract` opgeslagen in het cache-JSON-bestand; resultaten gecachet in `article_cache/`
- `.claude/feedreader-learn.py` — leerloop: verwerkt skip-queue, matcht Zotero-toevoegingen, geeft drempeladvies (continu proces)
- `.claude/score_log.jsonl` — groeiend logboek (URL, score, bron, source_type, timestamp, added_to_zotero, skipped)
- `.claude/skip_queue.jsonl` — wachtrij van expliciet afgewezen items (👎); dagelijks verwerkt door feedreader-learn.py
- `.claude/transcript_cache/` — JSON-cache van transcripten en show notes; YouTube: `{video_id}.json`; podcast: `podcast_{episode_id}.json`; na artikelgeneratie bevat het cache-bestand ook een `abstract`-veld met de volledige artikeltekst
- `.claude/article_cache/` — HTML-cache van gegenereerde artikelen; YouTube: `{video_id}.html`; podcast: `podcast_{episode_id}.html`
- `~/.local/share/feedreader-serve/` — serveermap (buiten Documents vanwege macOS TCC)

**URLs (lokale HTTP-server op poort 8765):**
- `http://localhost:8765/filtered.html` — HTML-lezer met score- en bronweergave + type-filterknoppen **Alles / 📄 / ▶️ / 🎙️** + **⌨️ terminal**-knop die een ttyd-terminal als iframe opent (poort 7681; iframe-URL gebaseerd op `window.location.hostname` zodat het ook werkt op iPad via het Mac-IP) (Mac/iPhone/iPad)
- `http://localhost:8765/filtered-webpage.xml` — Atom-feed webartikelen voor NetNewsWire
- `http://localhost:8765/filtered-youtube.xml` — Atom-feed YouTube voor NetNewsWire
- `http://localhost:8765/filtered-podcast.xml` — Atom-feed podcasts voor NetNewsWire
- `http://localhost:8765/article/{video_id}` — gegenereerd leesartikel voor een YouTube-video (structuur: Inleiding · Kernpunten · Conclusie; taal = originele videotaal)
- `http://localhost:8765/article/podcast/{episode_id}` — gegenereerd leesartikel voor een podcast-aflevering op basis van show notes (zelfde structuur; alleen voor afleveringen met show notes ≥ 200 tekens)

**Scores en labels:** 🟢 ≥50 · 🟡 40–49 · 🔴 <40 (drempels worden bijgesteld via feedreader-learn.py)

**Handmatig uitvoeren:**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-score.py
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

**👎-knop:** elk item in de HTML-lezer heeft een 👎-knop. Klikken markeert het item als `skipped: true` in het logboek (via de server) en visueel als doorgestreept. Dit is een sterk expliciet negatief signaal, onderscheiden van "niet aangeklikt" (ambigu).

**Leerloop:** feedreader-learn.py verwerkt eerst de skip-queue (👎-signalen), matcht daarna recent aan Zotero toegevoegde items aan het logboek, en onderscheidt drie categorieën: ✅ positieven · 👎 expliciet afgewezen · ❌ zwak negatief (niet toegevoegd na timeout). Na ≥30 positieven verschijnt een initieel drempeladvies; pas dan `THRESHOLD_GREEN` en `THRESHOLD_YELLOW` in `feedreader-score.py` aan. Het leren gaat daarna continu door.

**launchd-daemons (alle drie in `/Library/LaunchDaemons/`, draaien zonder ingelogde gebruiker):**
- `nl.researchvault.feedreader-server` — HTTP-server permanent actief (poort 8765); log: `~/Library/Logs/feedreader-server.log`
- `nl.pietstam.nachtelijke-taken` — nachtelijke batchrun dagelijks om 06:00: zotero update-db → feedreader-score → feedreader-learn → shutdown; Mac wordt gewekt via `pmset wakeorpoweron` om 05:55; log: `~/Library/Logs/nachtelijke-taken.log`
- `nl.researchvault.ttyd` — browser-terminal permanent actief (poort 7681, `--writable`); log: `~/Library/Logs/ttyd.log`

## RSS-feeds
- RSS-feeds worden gefilterd door de feedreader; de HTML-lezer (`http://localhost:8765/filtered.html`) of de Atom-feed in NetNewsWire toont items gesorteerd op relevantiescore
- Feeds toevoegen: zet de feed-URL op een nieuwe regel in `.claude/feedreader-list.txt`
- Academische artikelen die interessant zijn: voeg ze toe aan Zotero via de browser-extensie of iOS-app → komen in `_inbox` terecht
- Niet-academische artikelen: voeg toe via Zotero Connector, of geef de URL door met `inbox [URL]` voor directe opslag als Markdown in `inbox/`
- Bestandsnaam voor RSS-items zonder Zotero-record: `[bron-jaar-kernwoord].md` met #tag `#web` of `#beleid`

## Spaced repetition (Obsidian plugin)
- Flashcards worden aangemaakt na elke literatuurnotitie of synthese
- Formaat: vraag en antwoord gescheiden door `?` op een nieuwe regel, omsloten door `#flashcard`-tag
- Maak maximaal 5 kaarten per bron — kies de meest relevante concepten
- Dagelijkse review via Obsidian Spaced Repetition plugin (zijbalk → Kaarten beoordelen)

## Privacyregel: broninhoud blijft lokaal

**Noch de volledige tekst van bronnen (papers, artikelen, transcripten), noch enige door het model gegenereerde tekst op basis daarvan (samenvattingen, parafrases, afgeleide tekst) mag ooit als output van een Bash-commando in Claude's context terechtkomen.** Zodra tekst als tool-output terugkomt, is hij naar de Anthropic API gegaan — ook als de intentie was om hem alleen lokaal te verwerken.

Correcte aanpak voor het genereren van literatuurnotities: gebruik `.claude/process_item.py`. Dit is de privacy-preserving subagent die de volledige lokale pipeline uitvoert en alleen een JSON-statusobject teruggeeft:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/process_item.py \
  --item-key ITEMKEY \
  --title "Titel" --authors "Achternaam, V." --year 2024 \
  --journal "..." --citation-key auteur2024kw \
  --zotero-url "zotero://select/library/items/ITEMKEY" \
  --tags "thema" --status unread
# → {"status": "ok", "path": "literature/auteur2024kw.md"}
```

De subagent roept intern `fetch-fulltext.py` en `ollama-generate.py` aan. Geen bron-inhoud bereikt Claude Code als tool-output.

Correcte aanpak voor compacte samenvattingen (fase 2, 📖-items): gebruik `.claude/summarize_item.py`. Zelfde privacy-patroon: de samenvatting wordt naar een lokaal bestand geschreven; alleen het pad wordt teruggegeven:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY \
  --type paper|youtube|podcast \
  --title "Titel" --authors "Achternaam, V." --year 2024
# → {"status": "ok", "path": "inbox/_summary_ITEMKEY.md"}
```

Claude Code toont het pad; de gebruiker leest het bestand en geeft Go of No-go.

Voor losse stappen of speciale gevallen (transcripten, snapshots): gebruik `.claude/fetch-fulltext.py` direct:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/fetch-fulltext.py ITEMKEY inbox/bestand.txt
```

Daarna verwerken via Ollama:
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input inbox/bestand.txt --output literature/bestand.md --prompt "..."
```

Dit geldt ook voor snapshot-HTML, VTT-transcripten en podcast-transcripten: nooit `cat` of `print` op de volledige inhoud uitvoeren als Bash-tool.

## Actieve skills
- Lees en volg `.claude/skills/SKILL.md` bij elke research-sessie.