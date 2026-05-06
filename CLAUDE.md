# CLAUDE.md — Werkwijze ResearchVault

> **Bevroren specificatie.** Pas dit bestand alleen aan na expliciete beslissing. Elke wijziging verandert het gedrag van alle toekomstige ingests en lint-runs.

## Gedragsregels voor Claude Code

- **Stel eerst vragen, neem niets aan.** Bij probleemanalyse en diagnose: stel gerichte vragen vóór je oorzaken of oplossingen formuleert. Werk iteratief: één hypothese tegelijk toetsen. Neem nooit situationele feiten aan (Ollama bereikbaar, Zotero draait, scriptpad klopt, config correct) zonder die eerst te verifiëren.
- **Plan eerst, voer pas uit na goedkeuring.** Presenteer bij elke voorgestelde wijziging (scripts, configuratie, bestanden) eerst het plan. Stel vragen als er keuzes te maken zijn. Voer pas iets door na expliciet akkoord.
- **Eén hypothese tegelijk.** Bij bugs of onverwacht gedrag: toets één oorzaak per stap. Maak niet meerdere wijzigingen tegelijk — dat maakt de oorzaak onherleidbaar.
- **"Update github" = wrap-up eerst.** Wanneer de gebruiker vraagt om naar GitHub te pushen ("update github", "push naar github", "commit en push" of soortgelijk), activeer dan altijd eerst `.claude/skills/wrap-up/SKILL.md` vóórdat je git-commando's uitvoert.

## Sessie-startup

Verifieer bij elke sessie vóór de eerste actie of de services beschikbaar zijn:

```bash
# Zotero bereikbaar?
curl -s http://localhost:23119/better-bibtex/cayw | head -c 80

# Ollama bereikbaar + qwen3.5:9b aanwezig?
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; m=[x['name'] for x in json.load(sys.stdin)['models']]; print('Ollama OK:', m)"
```

Als Zotero niet bereikbaar is: meld dit direct en vraag of de sessie zinvol is zonder Zotero-toegang.
Als Ollama niet bereikbaar is: meld dit en vraag of de gebruiker wil overschakelen naar `--hd` (Anthropic API) of de sessie wil uitstellen.

## Obsidian-conventies
- Alle bestanden zijn Markdown (.md)
- Gebruik [[dubbele haken]] voor interne links tussen notes
- Gebruik #tags voor thematische categorisatie
- Bestandsnamen canonical bundles: `{citekey}__{itemKey}.md` (dubbele underscore; `build-zotero-bundle.py` genereert automatisch)

## Vault-structuur

| Map | Paginatype | Inhoud |
| --- | --- | --- |
| `vault/raw/` | Canonical bundles | Één bundle per Zotero-item: verbatim notes + annotaties + volledige tekst |
| `vault/wiki/sources/` | Wiki-bronnen | kytmanov-gegenereerde kruisverwijzingen (lees-only) |
| `vault/wiki/syntheses/` | Syntheses | Thematische syntheses van meerdere bronnen |
| `vault/wiki/concepts/` | Concepts | LLM-onderhouden conceptpagina's |
| `vault/authoring/notes/` | — | Persoonlijke werknotities (via symlink → myfiles/notes/) |
| `vault/.cache/` | — | Tijdelijke verwerkingsbestanden (transcripts, audio) |

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
- Genereer canonical bundle: `python3 .claude/build-zotero-bundle.py --item-key ITEMKEY`
- Bundle wordt opgeslagen in `vault/raw/{citekey}__{itemKey}.md`

## Ingest-procedure

**Pipeline (geen LLM in de bundle-stap):**
```
Zotero (PDFs, annotaties, child notes)
    ↓ build-zotero-bundle.py  [geen LLM — puur format-conversie]
vault/raw/{citekey}__{itemKey}.md
    ↓ olw ingest (gemma3:12b)
vault/wiki/sources/{titel}.md
    ↓ olw compile (mistral-small:22b)
vault/wiki/concepts/{concept}.md
```

**Stap 1 — Kwaliteitscheck**
Beoordeel of het item de vault waard is via `index-score.py`. Items met score < 40 (🔴) worden niet ingested tenzij er een expliciete reden is.

**Stap 2 — Canonical bundle aanmaken**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py \
  --item-key ITEMKEY
# → {"status": "ok", "path": "vault/raw/{citekey}__{ITEMKEY}.md"}
```
Haalt verbatim op: metadata, abstract, child notes (HTML→MD), PDF-annotaties (per pagina), volledige PDF-tekst. Geen LLM betrokken. Geen bron-inhoud bereikt Claude Code.

**Stap 3 — kytmanov verwerkt nieuwe bundles**
```bash
(cd vault && olw ingest)   # verwerkt vault/raw/ → wiki/sources/ + wiki/concepts/
```

**Stap 4 — Human review (optioneel)**
```bash
(cd vault && olw review)   # approve/reject per draft in wiki/.drafts/
```

**YouTube-transcripten (eager pipeline):**
Bij ✅ in de feedreader eerst transcript-bijlage aanmaken vóór Go/No-go:
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py ITEMKEY
```
Daarna `build-zotero-bundle.py` uitvoeren — het script leest de bijlage via `fetch-fulltext.py`.

**Ollama-routing:**
- Bundle-aanmaak → geen Ollama (pure format-conversie)
- kytmanov ingest/compile → gemma3:12b (fast) / mistral-small:22b (heavy)
- Coördinatie, beslissingen, review → Claude (orchestrator)
- Navigatie, zoeken → hyalo (geen LLM)

## kytmanov / obsidian-llm-wiki (wiki.toml)

kytmanov (PyPI: `obsidian-llm-wiki`, CLI: `olw`) is de wiki-compiler die LLM-notities omzet naar een kennisgraaf. Besluit genomen 2026-05-04. Configuratie: `wiki.toml` in de vault-root.

**Architectuurlaag:**

| Laag | Map | Beheerd door |
|---|---|---|
| Immutable originals | Zotero (PDFs, transcripts) | Zotero |
| Canonical bundles | `vault/raw/` | `build-zotero-bundle.py` (geen LLM) |
| Wiki output | `vault/wiki/sources/` + `vault/wiki/concepts/` | kytmanov (`olw`) |

**Modellen (via Ollama):** `gemma3:12b` (fast) · `mistral-small:22b` (heavy). Let op: `qwen3.5:9b` is incompatibel — thinking mode produceert lege respons bij `format=json`.

**Gebruik** (vanuit repo-root — `olw` zoekt `wiki.toml` in `vault/`):
```bash
(cd vault && olw ingest)    # verwerk nieuwe raw/ bundles naar wiki/sources/ + wiki/concepts/
(cd vault && olw build)     # herbouw alle conceptpagina's
(cd vault && olw clean)     # GEVAARLIJK: wist volledig vault/wiki/ — nooit uitvoeren
```

**Veiligheidsregel:** `vault/raw/` staat NIET onder `vault/wiki/`. `olw clean` wist de volledige `vault/wiki/`-map — bundles in `vault/raw/` zijn daartegen beschermd door hun locatie.

**Lokale state (.gitignore):** `vault/.olw/` · `vault/wiki/chroma` · `vault/wiki/state.db`

## _inbox prioritering (index-score.py)
- Gebruik `.claude/index-score.py` om items in de Zotero `_inbox` te scoren op relevantie vóór de fase 2-review
- Het script vergelijkt de embeddings van inbox-items met het gewogen gemiddelde van je bestaande bibliotheek (via ChromaDB, model: all-MiniLM-L6-v2)
- Items met PDF-annotaties in Zotero wegen zwaarder mee in het voorkeursprofiel (gewicht 3 vs. 1)
- Uitvoeren: `~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py`
- Output: gesorteerde lijst met scores 0–100, labels 🟢 (≥70) · 🟡 (40–69) · 🔴 (<40)

## Zotero-hulpscripts
- `.claude/zotero-inbox.py` — leest alle items uit de Zotero `_inbox` collectie via de lokale REST API (localhost:23119); gebruik voor overzicht of scripting: `python3 zotero-inbox.py --json`; vereist dat Zotero draait
- `.claude/zotero-remove-from-inbox.py` — verwijdert een item uit de `_inbox` na verwerking:
  ```bash
  ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
  ```
- `.claude/zotero_utils.py` — gedeelde SQLite-hulpfuncties voor feedreader-score.py, feedreader-learn.py en index-score.py; leest items en gewichten direct uit de Zotero-database (geen API-aanroepen)

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

**Na Go: canonical bundle aanmaken via `build-zotero-bundle.py`** — het script leest de transcript-bijlage automatisch via `fetch-fulltext.py` (zie Ingest-procedure).

**Bundelinhoud voor video/podcast:**
- Abstract: de door `attach-transcript.py` gegenereerde samenvatting (3–5 zinnen)
- Volledige tekst: het transcript zoals opgeslagen als Zotero-bijlage

**Fallback:** `fetch-fulltext.py` leest de transcript-bijlage uit het Zotero-item (lokale API); yt-dlp is niet meer nodig voor de pipeline.

## Zotero database-onderhoud
- De semantische zoekdatabase wordt automatisch bijgewerkt dagelijks om 06:00 via de nachtelijke-taken daemon (`nl.pietstam.nachtelijke-taken`) — geen handmatige actie nodig vóór een sessie
- Herinner de gebruiker eraan de database handmatig bij te werken als zoekopdrachten recente toevoegingen missen die van dezelfde dag zijn (de automatische update draait om 06:00)
- Gebruik het commando `update-zotero` (alias) of `zotero-mcp update-db --fulltext` voor een handmatige volledige update
- Check de status met `zotero-status` of `zotero-mcp db-status`

## Podcast-transcripten (whisper.cpp + yt-dlp)
- Audio wordt gedownload via yt-dlp en opgeslagen in `vault/.cache/` als `.mp3`
- Transcriptie verloopt lokaal via whisper.cpp (volledig offline)
- Whisper detecteert de taal automatisch; geef `--language` alleen expliciet mee als de automatische detectie onjuist is
- Verwerk een transcript naar een bundle via `build-zotero-bundle.py` of sla op in `vault/.cache/` als tijdelijk bestand met de volgende structuur:
  - Titel, spreker(s), programma/kanaal, datum, URL of bronvermelding
  - Samenvatting (3–5 zinnen)
  - Kernpunten met tijdcodes
  - Relevante uitspraken (met tijdcode, in de originele taal)
  - Links naar gerelateerde notes in de vault
- Bestandsnaam voor podcast-notes: `[spreker-jaar-kernwoord].md` met #tag `#podcast`
- Bij lange podcasts (> 45 min): maak eerst een gelaagde samenvatting (hoofdlijn → per segment)
- Ruwe `.mp3` en `.txt`-bestanden verwijder je uit `vault/.cache/` nadat de note is aangemaakt

## Feedreader — RSS-filtering (feedreader-score.py)

De feedreader scoort RSS/YouTube/podcast-feeds automatisch op relevantie en produceert een gefilterde HTML-lezer en Atom-feed. Het is de automatische filterfunctie binnen fase 1 van de workflow. Draait dagelijks via launchd.

**Bestanden:**
- `.claude/feedreader-list.txt` — lijst van feed-URLs (één per regel, `#` = commentaar); bevat webartikel-, YouTube- en podcast-feeds ingedeeld per categorie met `# ── Naam ────` headers
- `.claude/feedreader-score.py` — haalt feeds op, scoort items, detecteert brontype; voor YouTube-items haalt het eerst een transcript op via `youtube_transcript_api` (gecachet in `transcript_cache/`) en gebruikt de transcripttekst voor de scoreberekening; voor podcast-items met show notes ≥ 200 tekens (constante `SHOWNOTES_MIN_LENGTH`) worden de show notes gecachet in `transcript_cache/podcast_{episode_id}.json` (`episode_id` = `podcast_` + MD5-hash van de URL); schrijft `filtered.xml` en `filtered.html`; elke Atom-feed bevat een `<link rel="self">` met de Tailscale HTTPS-URL (poort 8443) zodat NetNewsWire de feed correct herkent bij toegang via Tailscale
- `.claude/feedreader_core.py` — gedeelde functies: `cosine_similarity`, `compute_weighted_profile`, `score_label`, `detect_source_type`, `bayesian_score`; constanten: `THRESHOLD_GREEN`, `THRESHOLD_YELLOW`, `THRESHOLD_STAR`, `PRIOR_RELEVANCE`, `WEIGHT_DEFAULT`, `WEIGHT_ANNOTATIONS`
- `.claude/freshrss_utils.py` — GReader API helpers: authenticatie, stream-fetch, auto-sterren; leest credentials uit `~/bin/.researchvault-env`
- `.claude/feedreader-server.py` — lokale HTTP-server (poort 8765); handelt `GET /action?type=skip` af (skip-queue) en serveert Atom-feeds en statische bestanden; genereert leesartikelen via Ollama voor YouTube/podcast
- `.claude/feedreader-learn.py` — leerloop: verwerkt skip-queue, haalt FreshRSS-signalen op (gestefd/gelezen), matcht Zotero-toevoegingen, geeft drempeladvies (continu proces)
- `.claude/score_log.jsonl` — groeiend logboek (URL, score, score_raw, bron, source_type, timestamp, added_to_zotero, skipped)
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

**Scores en labels:** 🟢 ≥50 · 🟡 40–49 · 🔴 <40 (Bayesiaanse scores met prior π=0.70; drempels worden bijgesteld via feedreader-learn.py). Items met score ≥70 worden auto-gestefd in FreshRSS/NNW.

**Handmatig uitvoeren:**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-score.py
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

**Leerloop — signaalhi­ërarchie (sterkste eerst):**
1. ⭐ NNW-ster (FreshRSS starred) → positief
2. ✅ Zotero URL-match of titelmatching → positief
3. 📖 NNW gelezen maar niet in Zotero na >1 dag → negatief
4. ❌ Timeout >3 dagen zonder actie → negatief (sterkste)
5. 👎 Skip-knop in NNW → sterk expliciet negatief (apart bijgehouden)

Na ≥30 positieven verschijnt een drempeladvies; pas dan `THRESHOLD_GREEN` en `THRESHOLD_YELLOW` aan.

**launchd-daemons (alle vier in `/Library/LaunchDaemons/`, draaien zonder ingelogde gebruiker):**
- `nl.researchvault.feedreader-server` — HTTP-server permanent actief (poort 8765); log: `~/Library/Logs/feedreader-server.log`
- `nl.pietstam.nachtelijke-taken` — nachtelijke batchrun dagelijks om 06:00: zotero update-db → feedreader-score → freshrss actualize → feedreader-learn → proton-backup → proton-mirror → shutdown; Mac wordt gewekt via `pmset wakeorpoweron` om 05:55 (5 min vóór de trigger; zie RUNBOOK.md voor race condition historie); log: `~/Library/Logs/nachtelijke-taken.log`; rclone heeft **Full Disk Access** nodig (Systeeminstellingen → Privacy en beveiliging → Volledige schijftoegang → `/opt/homebrew/bin/rclone`) — zonder FDA blokkeert macOS TCC de toegang tot `~/Documents` stil tijdens headless runs; **veiligheidsregel: de shutdown-stap vuurt alleen als `LAUNCHD_RUN=1` gezet is (door de plist) — handmatig uitvoeren van het script sluit de Mac nooit af**
- `nl.pietstam.overdagtaken` — dagbatchrun op 09:00, 12:00, 15:00, 18:00 en 21:00: stappen 1–4 (zotero update-db → feedreader-score → freshrss actualize → feedreader-learn); sluit de Mac alleen af na de 21:00-run én alleen als er geen actieve gebruikerssessie is; log: `~/Library/Logs/overdagtaken.log`
- `nl.researchvault.ttyd` — browser-terminal permanent actief (poort 7681, `--writable`); log: `~/Library/Logs/ttyd.log`

> **FreshRSS-setup (huidige configuratie — Option C):** FreshRSS draait in Docker op Home Assistant Green (altijd aan), niet op de Mac Mini. De actualize-stap in `nachtelijke-taken.sh` stuurt een HTTP curl-verzoek naar het HA Green Tailscale IP (poort 8080) — geen `docker exec`. FreshRSS haalt de feeds vervolgens op van de Mac Mini (poort 8765 via Tailscale). De Mac Mini kan daarna afsluiten; FreshRSS op HA Green blijft de items de rest van de dag serveren. NetNewsWire verbindt via het HA Green Tailscale IP.

## RSS-feeds
- RSS-feeds worden gefilterd door de feedreader; de HTML-lezer (`http://localhost:8765/filtered.html`) of de Atom-feed in NetNewsWire toont items gesorteerd op relevantiescore
- Feeds toevoegen: zet de feed-URL op een nieuwe regel in `.claude/feedreader-list.txt`
- Academische artikelen die interessant zijn: voeg ze toe aan Zotero via de browser-extensie of iOS-app → komen in `_inbox` terecht
- Niet-academische artikelen: voeg toe via Zotero Connector of de iOS share sheet — alle bronnen komen via de Zotero `_inbox` de vault in

## Architectuurprincipes (niet onderhandelbaar)

- **Privacy-grens**: source content (volledige tekst van papers, podcasts, video's) gaat NOOIT naar de Anthropic API. Alleen JSON status-objecten en metadata mogen Claude Code bereiken vanuit de subagents.
- **Subagent-patroon**: `build-zotero-bundle.py` en `summarize_item.py` worden aangeroepen als lokale Python-subprocessen. Claude Code stuurt ze aan maar voert zelf geen inhoudsverwerking uit.
- **`--hd` flag**: activeert Claude Sonnet 4.6 in plaats van Qwen3.5:9b. Vereist altijd expliciete bevestiging van de gebruiker vóór verzending naar de API.
- **Zotero**: alle interacties via de lokale REST API (localhost:23119) — vereist dat de Zotero app draait. Nooit via de Zotero Web API of andere cloud-diensten.
- **Ontwikkelsessies**: ook tijdens het schrijven of testen van nieuwe scripts gelden dezelfde privacyregels. Test nooit met echte paper-inhoud als die inhoud als tool-output in Claude's context kan komen. Gebruik synthetische testdata of alleen metadata bij ontwikkeling en debugging.

## Privacyregel: broninhoud blijft lokaal

**Noch de volledige tekst van bronnen (papers, artikelen, transcripten), noch enige door het model gegenereerde tekst op basis daarvan (samenvattingen, parafrases, afgeleide tekst) mag ooit als output van een Bash-commando in Claude's context terechtkomen.** Zodra tekst als tool-output terugkomt, is hij naar de Anthropic API gegaan — ook als de intentie was om hem alleen lokaal te verwerken.

Correcte aanpak voor het genereren van canonical bundles: gebruik `.claude/build-zotero-bundle.py`. Dit is de privacy-preserving subagent die alle Zotero-data samenvoegt zonder LLM-tussenkomst en alleen een JSON-statusobject teruggeeft:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py \
  --item-key ITEMKEY
# → {"status": "ok", "path": "vault/raw/{citekey}__{ITEMKEY}.md"}
```

Het script roept intern `fetch-fulltext.py` aan voor de PDF-tekst. Geen bron-inhoud bereikt Claude Code als tool-output.

Correcte aanpak voor compacte samenvattingen (fase 2, 📖-items): gebruik `.claude/summarize_item.py`. Zelfde privacy-patroon: de samenvatting wordt naar een lokaal bestand geschreven; alleen het pad wordt teruggegeven:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY \
  --type paper|youtube|podcast \
  --title "Titel" --authors "Achternaam, V." --year 2024
# → {"status": "ok", "path": "vault/.cache/_summary_ITEMKEY.md"}
```

Claude Code toont het pad; de gebruiker leest het bestand en geeft Go of No-go.

Voor losse stappen of speciale gevallen (transcripten, snapshots): gebruik `.claude/fetch-fulltext.py` direct:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/fetch-fulltext.py ITEMKEY vault/.cache/bestand.txt
```

Daarna verwerken via Ollama (alleen voor losstaande stappen buiten de bundle-pipeline):
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input vault/.cache/bestand.txt --output vault/.cache/bestand.md --prompt "..."
```

Dit geldt ook voor snapshot-HTML, VTT-transcripten en podcast-transcripten: nooit `cat` of `print` op de volledige inhoud uitvoeren als Bash-tool.

## Actieve skills
- Lees en volg `.claude/skills/SKILL.md` bij elke research-sessie.
- `.claude/skills/wrap-up/SKILL.md` — activeer bij "update github" of `/wrap-up`.