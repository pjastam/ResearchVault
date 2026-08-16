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

# Ollama bereikbaar + mistral-small:22b aanwezig (olw-model; qwen3.5:9b voor fallback-scripts)?
curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; m=[x['name'] for x in json.load(sys.stdin)['models']]; print('Ollama OK:', m)"
```

Als Zotero niet bereikbaar is: meld dit direct en vraag of de sessie zinvol is zonder Zotero-toegang.
Als Ollama niet bereikbaar is: meld dit en vraag of de gebruiker wil overschakelen naar `--hd` (Anthropic API) of de sessie wil uitstellen.

## Obsidian-conventies
- Alle bestanden zijn Markdown (.md)
- Gebruik [[dubbele haken]] voor interne links tussen notes
- Gebruik #tags voor thematische categorisatie
- Bestandsnamen: gebruik koppeltekens, geen spaties
  - `raw/`-bundles: `{citekey}__{itemKey}.md` (door `build-zotero-bundle.py`); `raw/notes/`: stabiele slug (door `promote-to-raw.py`)
  - `wiki/`-pagina's: naam = het concept/de bron, door olw gegenereerd — niet handmatig opgeven

## Vault-structuur

| Map | Paginatype | Inhoud |
| --- | --- | --- |
| `raw/` | Canonieke bronlaag | Één bundle per Zotero-item (`{citekey}__{itemKey}.md`) — verbatim frontmatter, abstract, notities, PDF-annotaties, volledige tekst; geen LLM-bewerking. De input voor olw. |
| `raw/notes/` | Eigen denkwerk | Gepromote snapshots van rijpe authoring-notities (via `promote-to-raw.py`), gemarkeerd `source_type: personal` |
| `wiki/` | olw-gegenereerd | Volledig door olw beheerd: conceptpagina's, `sources/` (per-bron), `syntheses/` (thematisch). Vervangt het oude `literature/`. `olw review` = de menselijke gate; `wiki/.drafts/` = staging vóór goedkeuring. |
| `authoring/notes/` | Eigen denkwerk (bron) | Symlink → Proton-app-map/`Notes` (Route A). Persoonlijke werknotities, bron voor `promote-to-raw.py`. `authoring/` is een echte map met per-item symlinks (venster, Mac-only, gitignored); géén vault-native `notes/`-map. |
| `.cache/` | — | Ruwe/temp input die nog verwerkt moet worden |

## Bronlaag (`raw/`) en wiki-pagina's

`build-zotero-bundle.py` schrijft per Zotero-item een canonieke bundle naar `raw/` met deze YAML-frontmatter (verbatim, geen LLM-bewerking):
```yaml
---
citekey: auteur2024kernwoord
zotero_item_key: ITEMKEY
title: "Volledige titel van het werk"
creators: ["Achternaam, Voornaam", ...]
year: "JJJJ"
journal: "Naam tijdschrift of uitgever"
zotero_uri: "zotero://select/library/items/ITEMKEY"
tags: [thema1, thema2]
source_type: paper|web|youtube|podcast
exported_at: JJJJ-MM-DD
---
```
Daarna volgen verbatim: abstract, Zotero-notities, PDF-annotaties per pagina, en de volledige geëxtraheerde tekst. Gepromote eigen notities (`raw/notes/`) dragen `source_type: personal` + `origin_uri`.

**Let op:** schrijf tags zónder `#` in de frontmatter (bijv. `[beleid, zorg]`). Obsidian voegt de `#` automatisch toe in de UI. Een `#` binnen een YAML-array breekt de frontmatter-parse.

**Wiki-pagina's worden door olw gegenereerd** uit de `raw/`-bundles (`olw compile`) en verschijnen eerst als drafts in `wiki/.drafts/`; jij keurt ze goed via **`olw review`** (de menselijke gate). De structuur en cross-links van de concept-/bronpagina's zijn olw's domein (aangestuurd via `wiki.toml`) — niet handmatig geschreven. Er zijn dus geen hand-geschreven literatuurnotities meer.

**Cross-link drempelwaarden** (leidraad, ook voor eigen aanvullingen): voeg een `[[link]]` toe als twee pagina's minstens twee gedeelde kernbegrippen delen, of bij een directe citatie-relatie. Geen links op oppervlakkige thema-overeenkomst alleen.

## Taal
- Antwoord in het Nederlands tenzij anders gevraagd
- Schrijf literatuurnotities in de taal van de originele bron (Engels artikel → Engelstalige note, Nederlands artikel → Nederlandstalige note)
- Citaten altijd in de originele taal

## Zotero-workflow
- Gebruik Zotero MCP om papers op te halen via hun titel of sleutelwoorden
- Verwerking loopt via de canonieke bronlaag: Zotero-item → `build-zotero-bundle.py` → `raw/{citekey}__{itemKey}.md` → `olw ingest` → `olw compile` → `olw review` → `wiki/`
- Zotero-tags komen mee in de bundle-frontmatter; olw beheert de wiki-pagina's (geen handmatige literatuurnotities meer)

## Ingest-procedure

olw compileert bestaande kennis — het genereert geen nieuwe kennis. De pijplijn draait lokaal; alleen JSON-status en tellingen bereiken Claude Code.

**Stap 1 — Kwaliteitscheck (fase 2)**
Beoordeel of het item de vault waard is via `index-score.py` (semantische relevantiescore t.o.v. je bibliotheek). Lage scores (🔴) worden niet ingest tenzij er een expliciete reden is.

**Stap 2 — Bundle bouwen (Go)**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py --item-key ITEMKEY
# → {"status": "ok",   "path": "vault/raw/{citekey}__{itemKey}.md", "woorden": 10686}
# → {"status": "leeg", "path": "...", "woorden": 2, "hint": "..."}   ← NIET ingesten
```
Voor eigen denkwerk: `promote-to-raw.py --note <pad>` → `raw/notes/`. Geen bron-inhoud bereikt Claude Code.

**Status `leeg` (sinds 15 aug 2026).** Draagt de bundle minder dan 300 woorden body, dan is er
geen bruikbare tekst en heeft ingesten geen zin — olw meldt dat niet zelf en levert dan nul of
enkele loze concepten. Oorzaak is bijna altijd dat Zotero het PDF niet heeft geïndexeerd:
`fetch-fulltext.py` haalt PDF-tekst uitsluitend uit Zotero's fulltext-index en kent geen
OCR-fallback. Steekproef van 15 aug 2026: van de niet-geïndexeerde PDFs heeft **90% wél een
tekstlaag** (herindexeren lost het op, Instellingen → Zoeken → index opnieuw opbouwen) en 10%
niet (gescand, OCR nodig). Controleer bij `leeg` dus eerst de index vóór je naar OCR grijpt.

**Stap 3 — Ingest + compile (olw)**
```bash
olw ingest vault/raw/{...}.md --vault vault   # concept-extractie
olw compile --vault vault                     # drafts → wiki/.drafts/
```
De feedreader-Go (`/api/inbox/go`) en `promote-to-raw.py` doen de ingest automatisch; `compile` draai je gebatcht (kan traag zijn — grote-context prefill).

**Modelkeuze staat niet in het commando.** Beide stappen lezen het model uit `vault/wiki.toml` — de enige modelbron (besluit A, 14 aug 2026). Tot dan droeg `wiki-backend.toml` een eigen `model`-sleutel die alleen tijdens ingest gold, waardoor een half doorgevoerde wissel ingest en compile stil op verschillende modellen zette. Geef `--fast-model` dus niet mee: dat overschrijft alleen ingest en herintroduceert precies die scheefstand.

**Stap 4 — Human review (de gate)**
```bash
olw review --vault vault
```
Per draft Go/No-go: approve → publiceren naar `wiki/`; reject → draft weg + rejection-feedback (voedt de leerloop). Claude leest geen draft-inhoud — jij beoordeelt in je eigen terminal.

**Stap 5 — Cross-links & syntheses**
olw legt cross-links en syntheses aan tijdens `compile`; `olw lint` / `olw maintain` bewaken de wiki-gezondheid (orphans, broken links, stubs).

**Backend-routing:**
- Concept-extractie, synthese, review-drafts → olw (mistral-small:22b, lokaal)
- Coördinatie, beslissingen, de review-gate → Claude (orchestrator) + jij
- Navigatie, zoeken, link management → hyalo (geen LLM)

## _inbox prioritering (index-score.py)
- Gebruik `.claude/index-score.py` om items in de Zotero `_inbox` te scoren op relevantie vóór de fase 2-review
- Het script vergelijkt de embeddings van inbox-items met het gewogen gemiddelde van je bestaande bibliotheek (via ChromaDB, model: all-MiniLM-L6-v2)
- Items met PDF-annotaties in Zotero wegen zwaarder mee in het voorkeursprofiel (gewicht 3 vs. 1)
- Uitvoeren: `~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py`
- Output: gesorteerde lijst met scores 0–100, labels 🟢 (≥70) · 🟡 (40–69) · 🔴 (<40)

## Zotero-hulpscripts
- `.claude/zotero-inbox.py` — leest alle items uit de Zotero `_inbox` collectie via de lokale REST API (localhost:23119); gebruik voor overzicht of scripting: `python3 zotero-inbox.py --json`; vereist dat Zotero draait
- `.claude/zotero-remove-from-inbox.py` — verwijdert een item uit de `_inbox` na verwerking via `zotero_api.py` (default: local API, vereist Zotero desktop):
  ```bash
  ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
  ```
- `.claude/zotero_utils.py` — gedeelde SQLite-hulpfuncties voor feedreader-score.py, feedreader-learn.py en index-score.py; leest items en gewichten direct uit de Zotero-database (geen API-aanroepen)
- `.claude/zotero_api.py` — unified Zotero API-client; kiest automatisch local of web op basis van `ZOTERO_ACCESS`; publieke API: `zotero_request(path, method, data, extra_headers)`; laadt vault `.env` voor web-modus credentials
- `.claude/enrich-inbox.py` — batch-verrijking van `_inbox`-items zonder `_enriched`-tag; alle Zotero-aanroepen via `zotero_api.py` (modus afhankelijk van `ZOTERO_ACCESS`: `web` in nachtelijke-taken, `auto` in overdagtaken, `local` interactief); per item: (1) metadata via CrossRef (DOI) of Open Graph (webartikel); (2) bijlage: OA-PDF via Unpaywall, HTML-snapshot, of voor podcast-items met show notes in feedreader-cache: show notes als `abstractNote` + tag `_enriched-shownotes`; VU EZProxy-URL in `extra` als fallback voor paywalled papers

## Transcripten (attach-transcript.py)

`attach-transcript.py` verwerkt zowel YouTube- als podcast-items: haalt audio/transcript op, genereert een abstract via de geconfigureerde LLM-backend (Ollama of MLX) en slaat het transcript als `.txt`-bijlage op in Zotero. Alle Zotero-aanroepen lopen via `zotero_api.py`. **Let op:** de **schrijf**acties (abstractNote-PATCH, transcript-bijlage, child-notes) vereisen `ZOTERO_ACCESS=web` — de lokale API (:23119) is read-only en geeft 501/400 op writes; de feedreader-Go draait deze stap daarom in web-modus (het lokale `.txt` wordt als `linked_file` gekoppeld).

**YouTube** — eager pipeline: bij ✅ in de feedreader wordt het transcript meteen opgehaald. Handmatig aanroepen:
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
  --item-key ITEMKEY --url "https://www.youtube.com/watch?v=..."
```
Gebruikt `YouTubeTranscriptApi` (of `transcript_cache/`); prefereert het transcript in `nl`/`en` en valt anders terug op elke beschikbare taal (nodig voor NL-bronnen als NOS/VPRO/NPO — `en`-only faalde daarop). Geconfigureerde LLM-backend genereert abstract.

**Podcast** — altijd handmatig (whisper.cpp vereist audio-download, duurt minuten):
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
  --item-key ITEMKEY --url "https://podcast-episode-pagina-url"
```
Dit doet:
1. Audio downloaden via directe MP3-URL uit feedreader-cache (`audio_url` uit RSS `<enclosure>`) of yt-dlp
2. Taal detecteren uit show notes in feedreader-cache (automatisch `--language nl` voor NL-podcasts); `--language` overschrijft dit
3. Transcriberen via `whisper-cli` (model: `large-v3-turbo`, Metal GPU, ~2–3 min per 30 min audio op M4)
4. Abstract genereren via Qwen; als `abstractNote` al gevuld is (show notes van `enrich-inbox.py`) → verplaatsen naar child note "Shownotes"
5. Transcript als `.txt`-bijlage naar Zotero; abstract als `abstractNote`; tag `_enriched-transcript`

Optioneel: `--whisper-model base` of `--language en` om defaults te overschrijven; `--force` om te hertranscriberen (overschrijft bestaand transcript-bestand, maakt geen duplicaat).

**Na Go: verwerk via `build-zotero-bundle.py` → `raw/` → olw** — zelfde als papers (zie Ingest-procedure). Het transcript zit als `.txt`-bijlage in het Zotero-item en komt zo mee in de bundle. olw genereert de wiki-pagina; timecodes/citaten worden niet als geverifieerde bron opgenomen.

**Fallback:** `fetch-fulltext.py` leest de transcript-bijlage uit het Zotero-item (lokale API).

## Zotero database-onderhoud
- De semantische zoekdatabase wordt automatisch bijgewerkt bij de eerstvolgende ochtend-login via de login-getriggerde nachtelijke-taken daemon (`nl.pietstam.nachtelijke-taken`; sinds Laag-1 login-getriggerd i.p.v. een 06:00-timer) — geen handmatige actie nodig vóór een sessie
- Herinner de gebruiker eraan de database handmatig bij te werken als zoekopdrachten recente toevoegingen missen die van dezelfde dag zijn (de automatische update draait bij de ochtend-login, niet meer opnieuw later op de dag behalve via de overdagtaken)
- Gebruik het commando `update-zotero` (alias) of `zotero-mcp update-db --fulltext` voor een handmatige volledige update
- Check de status met `zotero-status` of `zotero-mcp db-status`

## Podcast-transcripten (whisper.cpp via attach-transcript.py)

Podcast-transcripten worden handmatig aangemaakt via `attach-transcript.py` (zie § Transcripten hierboven). Whisper.cpp draait volledig lokaal (Metal GPU, geen data naar buiten). Audio wordt tijdelijk opgeslagen in `.cache/` als `_audio_{ITEMKEY}.mp3` en na verwerking automatisch opgeruimd.

**Taaldetectie:** whisper-cli detecteert de taal automatisch op basis van de show notes in de feedreader-cache. Voor Nederlandstalige podcasts wordt `--language nl` automatisch doorgegeven; voor Engelstalige podcasts (Engelse show notes) wordt niets meegegeven (whisper auto-detect). Gebruik `--language` om dit handmatig te overschrijven.

**Tip:** als yt-dlp faalt met "Unsupported URL", voeg de feed toe aan `feedreader-list.txt`; na de volgende feedreader-score.py-run is de directe audio-URL gecachet en werkt de download zonder yt-dlp.

**Na transcriptie:** verwerk via `build-zotero-bundle.py` → `raw/` → olw (zelfde als papers, zie Ingest-procedure). Het transcript zit als bijlage in het Zotero-item en komt mee in de bundle.

## Feedreader — RSS-filtering (feedreader-score.py)

De feedreader scoort RSS/YouTube/podcast-feeds automatisch op relevantie en produceert een gefilterde HTML-lezer en Atom-feed. Het is de automatische filterfunctie binnen fase 1 van de workflow. Draait dagelijks via launchd.

**Bestanden:**
- `.claude/feedreader-list.txt` — lijst van feed-URLs (één per regel, `#` = commentaar); bevat webartikel-, YouTube- en podcast-feeds ingedeeld per categorie met `# ── Naam ────` headers
- `.claude/feedreader-score.py` — haalt feeds op, scoort items, detecteert brontype; voor YouTube-items haalt het eerst een transcript op via `youtube_transcript_api` (gecachet in `transcript_cache/`) en gebruikt de transcripttekst voor de scoreberekening; voor podcast-items met show notes ≥ 200 tekens (constante `SHOWNOTES_MIN_LENGTH`) worden de show notes gecachet in `transcript_cache/podcast_{episode_id}.json` (`episode_id` = `podcast_` + MD5-hash van de URL); slaat tevens de directe audio-URL op uit de RSS `<enclosure>`-tag als `audio_url`-veld (gebruikt door `attach-transcript.py` voor directe MP3-download); schrijft `filtered.xml` en `filtered.html`. De gegenereerde Atom-feeds dragen een channel home-`<link rel="alternate">` naar `{FEEDREADER_PUBLIC_URL}/filtered.html`, waarbij `FEEDREADER_PUBLIC_URL` (de publieke Tailscale-Funnel-basis van de Mini op poort **8443**) uit de omgeving of `~/bin/.researchvault-env` komt — leeg = geen link. Zonder die link slaat FreshRSS geen `htmlUrl` op en raadt NNW de kale poort-443-root (`https://<host>/`), die faalt omdat de funnel alleen op `:8443` luistert (cosmetische "HTML Metadata: TLS error"/"could not connect" in de NNW Activity Log)
- `.claude/feedreader_core.py` — gedeelde functies: `cosine_similarity`, `compute_weighted_profile`, `score_label`, `detect_source_type`, `bayesian_score`; constanten: `THRESHOLD_GREEN`, `THRESHOLD_YELLOW`, `THRESHOLD_STAR`, `PRIOR_RELEVANCE`, `WEIGHT_DEFAULT`, `WEIGHT_ANNOTATIONS`
- `.claude/feedreader_fetch.py` — ophaallaag met eigen HTTP-verzoek, tijdslimiet en herkansing. `fetch_feed()` onderscheidt vier uitkomsten: `ok` (items aanwezig), `leeg` (feed-titel maar geen items — een echt lege feed), `mislukt` (géén titel én géén items, dus de XML is niet geparsed) en `timeout`. Alleen de twee faaltoestanden worden herkanst (`FETCH_RETRIES = 1`, `FETCH_RETRY_DELAY = 2.0`); feeds met een gezette `bozo`-vlag maar bruikbare items gelden als geslaagd. Drie problemen waren de aanleiding:
  1. **Stille netwerkfouten** — `feedparser.parse()` werpt geen exceptie maar geeft een leeg object terug, waardoor mislukte fetches als "0 items" in het log verdwenen, ononderscheidbaar van een feed die niets publiceerde.
  2. **Geen tijdslimiet** — `FEED_TIMEOUT` in `feedreader-score.py` was dode code; feedparser's eigen downloader krijgt er geen mee, dus een server die de verbinding openhield kon de hele scoring-stap laten hangen tot `run_timeout 600` in `nachtelijke-taken.sh` ingreep — waarmee niet één maar álle feeds verloren gingen. Daarom doen we het HTTP-verzoek nu zelf, met expliciete time-out.
  3. **gzip met rommel erachter** — `_maybe_gunzip()` kijkt naar de gzip-magic bytes in plaats van naar `Content-Encoding` (servers liegen daarover) en pakt in twee trappen uit: eerst `gzip.decompress()` (handelt ook aaneengeschakelde leden correct af), en als die weigert omdat er ná de stroom nog bytes staan, een redding via `zlib.decompressobj(31)`. Vastgesteld bij piratenpartij.nl, waar een caching-plugin 220 bytes platte HTML achter de gzip-stroom plakt. Die feed is op 1 aug 2026 uit de lijst gehaald omdat hij dood leek; of déze bug daarvan de oorzaak was, is niet vastgesteld. Let bij zulke diagnoses ook op redirects: `piratenpartij.nl/rss` is een lege 301 naar `/feed/`, dus een client die redirects niet volgt (curl zonder `-L`, of een browser die de body van de redirect aanbiedt als download) ziet een leeg bestand terwijl de feed prima werkt.

  Downloader en parser zijn injecteerbaar en `feedparser` wordt lazy geïmporteerd, zodat `test_feedreader_fetch.py` op kale stdlib draait (CI heeft geen pip-install-stap). **Let op:** `import feedparser` in `feedreader-score.py` is daar niet lokaal in gebruik maar moet blijven staan — `backfill-scout.py` benadert het via `fr.feedparser`
- `.claude/test_feedreader_fetch.py` — unittests voor de ophaallaag (nep-downloader en nep-parser, geen netwerk); draait mee in de `tests`-workflow
- `.claude/feedreader_identity.py` — bepaalt wanneer twee feed-items hetzelfde item zijn. Drie functies: `canonical_url()` strijkt trackingparameters weg, `item_identity()` kiest guid-vóór-link, `item_keys()` levert de sleutelverzameling waarop wordt vergeleken. Alleen stdlib, zodat de tests op kale stdlib draaien (net als `feedreader_fetch.py`). Aanleiding waren drie los van elkaar staande defecten (gemeten 16 aug 2026 over 13.267 logregels):
  1. **Onstabiele link tussen runs** — de identiteit was de ruwe `entry.link`, en PubMed plakt bij elke fetch `ff=<timestamp>` aan de URL. Daardoor gold hetzelfde artikel elke run als nieuw, kreeg het een nieuwe Atom-`<id>` en verscheen het opnieuw in NetNewsWire. Eén erratum stond 43× in het log — precies het aantal runs sinds 1 aug. Goed voor 502 van de 651 overtollige logregels.
  2. **Geen deduplicatie bínnen een run** — een publicatie in de PURE-feeds van twee co-auteurs (bijv. Cattel én Van Kleef) kwam tweemaal in de output; 69 gevallen. De ruwe URLs zijn daar identiek, dus dit stond los van punt 1.
  3. **Stil verlies bij podcasts** — Captivate/RedCircle geven bij élke aflevering de showpagina als link (`doe-duurzaam.nl/de-groene-nerds-podcast/`, `homeassistant.fm/`). Een URL-sleutel zag aflevering 2 daardoor als duplicaat van aflevering 1 en gooide hem weg.

  **Beleid: denylist, niet allowlist.** Onbekende parameters blijven staan; falen richting duplicaten (zichtbaar) in plaats van richting stil verlies. `TRACKING_PARAMS` bevat alleen wat gemeten is: `ff`/`fc` (PubMed), de UTM-familie, `dgcid` (ScienceDirect, altijd `rss_sd_all`), `af` (Wiley/Health Affairs, altijd `R`), `awCollectionid`/`awEpisodeid` (NPO — redundant, het pad draagt het aflevering-id al), plus `fbclid`/`gclid` preventief. `v` staat **niet** globaal op de lijst maar per host (`TRACKING_PARAMS_PER_HOST`): op PubMed is het een API-versienummer, op YouTube de video-identiteit (277 waarden op één pad `/watch`).

  **Guid vóór link.** De RSS-`<guid>` is op elke gemeten feed minstens zo goed als de link: PubMed `pubmed:42461057` (stabiel), YouTube `yt:video:…`, Captivate een UUID per aflevering, PURE = de link zelf (en beide co-auteurfeeds geven dezelfde guid, dus cross-feed samenvallen blijft werken).

  **`link_is_shared` — de subtiliteit.** Een item draagt twee sleutelvormen: de guid-vorm én de canonieke URL. Die tweede is nodig omdat logregels van vóór 16 aug 2026 alleen URLs kennen; zonder die vorm zou de eerste run na de wissel élk item als nieuw zien — nog een volledige duplicatengolf. Maar bij de podcasts van punt 3 zou de URL-vorm afleveringen laten botsen. Daarom telt `feedreader-score.py` per `(feed, canonieke link)`: komt dezelfde link binnen één feed meer dan één keer voor, dan onderscheidt hij niets en valt dat item terug op alleen de guid. De teller is bewust op *(feed, link)* gesleuteld en niet op de link alleen — zo telt dezelfde publicatie in twee co-auteurfeeds in elke feed als 1 en blijft de URL-vorm daar bruikbaar.
- `.claude/test_feedreader_identity.py` — 37 unittests (geen netwerk); de regressietests gebruiken letterlijk de twee erratum-URLs uit `score_log.jsonl`. Draait mee in de `tests`-workflow
- `.claude/freshrss_utils.py` — GReader API helpers: authenticatie, stream-fetch, auto-sterren; leest credentials uit `~/bin/.researchvault-env`
- `.claude/feedreader-server.py` — lokale HTTP-server (poort 8765); handelt `GET /action?type=skip` af (skip-queue) en serveert Atom-feeds en statische bestanden; genereert leesartikelen via Ollama voor YouTube/podcast; biedt ook de inbox-review REST API (zie URLs hieronder)
- `.claude/feedreader-learn.py` — leerloop: verwerkt skip-queue, haalt FreshRSS-signalen op (gestefd/gelezen), matcht Zotero-toevoegingen, geeft drempeladvies (continu proces)
- `.claude/score_log.jsonl` — groeiend logboek (URL, identity, score, score_raw, bron, source_type, timestamp, added_to_zotero, skipped). `identity` (sinds 16 aug 2026) is de sleutel waarop volgende runs ontdubbelen; `url` blijft de ruwe link ernaast staan — dat is de link om te openen, en `feedreader-learn.py` matcht daar FreshRSS-signalen op. Oudere regels dragen geen `identity`; `load_existing_log()` canonicaliseert die bij het inlezen alsnog, dus het logboek is niet herschreven
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
- `http://localhost:8765/inbox` — inbox-review pagina (iPad-vriendelijk): toont Zotero `_inbox`-items gesorteerd op score met Go/No-go knoppen; Go → `build-zotero-bundle.py` → `raw/` + `olw ingest` + verwijder uit `_inbox`; No-go → verwijder direct uit `_inbox`. Bevat tevens een bulk-knop in de header (**✅ Alle ✅-items → Go (N)**) die alle openstaande `✅`-getagde items in één keer via het bestaande per-item `/api/inbox/go`-endpoint queuet (sequentieel, doorgaan-bij-fout; verschijnt alleen bij N>0)

**Inbox-review REST API (POST vereist `Content-Type: application/json`):**
- `GET  /api/inbox/items` — gecombineerde score + Zotero metadata per `_inbox`-item (JSON)
- `GET  /api/inbox/jobs` — status van alle achtergrond-jobs (`pending`/`running`/`done`/`error`)
- `GET  /api/inbox/summary/{key}` — leest `.cache/_summary_{key}.md` als die bestaat
- `POST /api/inbox/go` — /research-pariteit: voor `videoRecording`/`podcast`/YouTube-items (gate op `type`, met `url` in body) eerst `attach-transcript.py` (web-modus), dan `build-zotero-bundle.py` + `olw ingest` (asynchroon); vereist `title` in body. Removal na succes via de web-API (de lokale API :23119 is read-only). Faalt de transcript-stap → job `error`, item blijft in `_inbox`
- `POST /api/inbox/nogo` — verwijdert `key` direct uit Zotero `_inbox` (synchroon, web-API)
- `POST /api/inbox/summarize` — start `summarize_item.py` voor `key` (asynchroon)

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
- `nl.pietstam.nachtelijke-taken` — login-getriggerde batchrun (sinds Laag-1, jul 2026; niet meer op een 06:00-timer): `morning-batch.sh` (LaunchAgent) schrijft `~/.cache/morning-trigger` bij je ochtend-login → deze daemon vuurt via `WatchPaths` en draait zotero update-db → enrich-inbox → feedreader-score → freshrss actualize → feedreader-learn; kickstart daarna `nl.pietstam.proton-taken` (proton-backup → time-machine → proton-mirror); aan het eind sluit `idle-shutdown.sh` de Mac af als je weg bent (FileVault vergrendelt zo bij afwezigheid/diefstal). Log: `~/Library/Logs/nachtelijke-taken.log`; rclone heeft **Full Disk Access** nodig (Systeeminstellingen → Privacy en beveiliging → Volledige schijftoegang → `/opt/homebrew/bin/rclone`) — zonder FDA blokkeert macOS TCC de toegang tot `~/Documents` stil tijdens headless runs; **veiligheidsregel: de idle-shutdown-stap sluit alleen echt af als `LAUNCHD_RUN=1` gezet is (door de plist) — handmatig uitvoeren van het script sluit de Mac nooit af**
- `nl.pietstam.overdagtaken` — dagbatchrun op 09:00, 12:00, 15:00, 18:00 en 21:00: stappen 1–5 (zotero update-db → enrich-inbox → feedreader-score → freshrss actualize → feedreader-learn); sluit de Mac alleen af na de 21:00-run én alleen als er geen actieve gebruikerssessie is; log: `~/Library/Logs/overdagtaken.log`
- `nl.researchvault.ttyd` — browser-terminal permanent actief (poort 7681, `--writable`); log: `~/Library/Logs/ttyd.log`

> **FreshRSS-setup (huidige configuratie — Option C):** FreshRSS draait als HA Community Add-on (einschmidt/freshrss, poort 7077) op Home Assistant Green (altijd aan), niet op de Mac Mini. De actualize-stap in `nachtelijke-taken.sh` stuurt een HTTP curl-verzoek naar het HA Green Tailscale IP (poort 7077) — geen `docker exec`. FreshRSS haalt de feeds vervolgens op van de Mac Mini (poort 8765 via Tailscale Funnel). De Mac Mini kan daarna afsluiten; FreshRSS op HA Green blijft de items de rest van de dag serveren. NetNewsWire verbindt via het HA Green Tailscale IP (poort 7077). **`base_url`** is ingesteld op `http://100.113.121.73:7077/` via HA → Instellingen → Apps → FreshRSS → Configuratie → Opties (niet via de FreshRSS web-UI — die is read-only voor deze parameter).

## RSS-feeds
- RSS-feeds worden gefilterd door de feedreader; de HTML-lezer (`http://localhost:8765/filtered.html`) of de Atom-feed in NetNewsWire toont items gesorteerd op relevantiescore
- Feeds toevoegen: zet de feed-URL op een nieuwe regel in `.claude/feedreader-list.txt`
- Academische artikelen die interessant zijn: voeg ze toe aan Zotero via de browser-extensie of iOS-app → komen in `_inbox` terecht
- Niet-academische artikelen: voeg toe via Zotero Connector of de iOS share sheet — alle bronnen komen via de Zotero `_inbox` de vault in

## Back-catalog scout (`backfill-scout.py`)

De feedreader is een **flow**-instrument (`MAX_AGE_DAYS_DEFAULT = 30`; YouTube-RSS cap ~15) — de **back-catalog (stock)** van een bron is onzichtbaar. `.claude/backfill-scout.py` vult die blinde vlek: het enumereert de historie van **één bron** en scoort elk item **met dezelfde methode als de feedreader** tegen het gewogen Zotero-profiel. Conceptueel de tweeling van `/roadmap-scout`. Aanroepbaar via `/backfill`.

**Single-source (geen batch):** elke run verwerkt precies één bron. Rationale: houdt YouTube-transcript-fetches per run onder de ~30/IP-grens (met verse VPN per run → nooit `IpBlocked`), geeft controle over IP-rotatie, en is uniform over de drie brontypes.

```bash
PY=~/.local/share/uv/tools/zotero-mcp-server/bin/python3
$PY .claude/backfill-scout.py --source youtube --target "McElreath" --enrich-top-n 25
$PY .claude/backfill-scout.py --source podcast --target "In Our Time" --max-items 150
$PY .claude/backfill-scout.py --source scholar --target "van de Ven"
```
`--target` = naam-substring (tegen `feedreader-list.txt`, hyphen/spatie-ongevoelig) of directe id/url.

- **youtube** — `yt-dlp --flat-playlist` enumereert; **twee-traps**: trap 1 titel-only (gratis), trap 2 transcript[:3000] voor de top-N (`--enrich-top-n`, throttled, block-aware — cache wordt niet vervuild bij IpBlocked). ⚠️-bucket = titel-only (skewt te hoog, niet-vergelijkbare schaal). yt-dlp hangt op sommige VPN-datacenter-exits → andere exit-node proberen.
- **podcast** — `feedparser` op de RSS; score = titel + show notes[:1000] (géén transcript; whisper blijft post-Go). Dunne show notes (<200) → ⚠️-bucket. Verhoog `--max-items` om voorbij de flow-dekking te komen.
- **scholar** — `feedparser` + `fetch_pure_metadata`; score = titel + abstract[:1000]. PURE-feed toont ~50 recente pubs (geen diepere historie) → **geconsolideerde per-auteur ranking**, géén dedupe.
- **Hergebruik:** laadt `feedreader-score.py` via `importlib` (hyphen → niet importeerbaar) en erft functies (`fetch_and_cache_transcript`-equivalent, `get_embeddings_for_keys`, `fetch_pure_metadata`, `strip_html`), profiel-opbouw én paden-constanten (deelt de transcript-cache). youtube/podcast deduppen tegen `score_log.jsonl` — via `fr.canonical_url()`, want `load_existing_log()` geeft sinds 16 aug 2026 identiteiten terug in plaats van ruwe URLs. yt-dlp levert geen RSS-guid, dus de canonieke URL is hier de enige berekenbare sleutelvorm; die staat ook in de set omdat `load_existing_log()` per logregel beide vormen opneemt.
- **Output:** rapport per bron naar `vault/.cache/backfill-<source>-<slug>-<datum>.md` (🟢 ≥50 / 🟡 40–49 / 🔴 rest / ⚠️). State in `.claude/backfill_state.json` (per `source:target`).
- **Privacy:** stdout = alleen een JSON-statusobject; bron-/transcripttekst wordt nooit geprint. Embeddings via lokale `sentence_transformers`, geen Anthropic-API.
- **Uitrol-plan/lessen:** `~/.claude/plans/backfill-scout-rollout.md` (o.a. de ~30/IP transcript-limiet en de two-stage-rationale).

## Stock-intake (back-catalog) — de tweede intake-dimensie

Naast de **flow** (nieuwe items via feedreader → 3 fasen) kent de vault een **stock**-as: de in
de loop der jaren verzamelde bronnen. Twee kwadranten met verschillende bewerking:

- **Curated stock — de eigen Zotero-back-catalog** (~9.4k items buiten `_inbox`): deze heeft
  fase 2 (Filter) al gehad — bewaren = impliciete Go. Er is **géén nieuw scoringsscript** nodig;
  hergebruik de bestaande Process-fase (`build-zotero-bundle.py` → `olw compile` → `olw review`),
  gericht op library-items i.p.v. `_inbox`. Omdat het corpus ~50× het Karpathy-schaalplafond is
  (~100–200 bronnen; index moet in context passen), gaat de intake **in golven, geprioriteerd op
  de signaalgradiënt**: annotatie-rijkdom (277 geannoteerde items = Golf 0) → profiel-relevantie
  (has-PDF wetenschappelijke laag ~2.311) → thema/collectie. De ~7.000 thin/web-items blijven
  **archief** (doorzoekbaar via hyalo), geen wiki-materiaal. De feedreader-scoring wordt hier
  hergebruikt als **rangschikker**, niet als Go/No-go-poort.
  Driver: `.claude/backfill-annotated.py` — selecteert de geannoteerde items (gewicht >
  `WEIGHT_DEFAULT`), slaat bestaande `raw/`-bundles over (idempotent) en sequencet
  `build-zotero-bundle.py` per item. Geen scoring: curated stock is al gefilterd.
  Draai eerst `--dry-run` (alleen tellen) of `--limit N` (bake-off).
- **Uncurated stock — externe historie** (YouTube/scholar/journal): draait via
  `backfill-scout.py` mét scoring + Go/No-go (zie de sectie hierboven). Dit is de stock-tweeling
  van de flow-filter.

**Leidend plan:** `plans/stock-intake.md` in de privé companion-repo (o.a. de meting, de golf-
strategie, en de model-bake-off — de back-catalog-migratie is het moment om het olw-model te
herzien: Mac mini M4/24 GB heeft ruimte boven `mistral-small:22b`; modelkeuze via bake-off op
eigen geannoteerd materiaal, niet op benchmarks). De olw-model-regel in deze CLAUDE.md wijzigt
pas na een expliciete bake-off-beslissing.

## Vertrouwelijke compartimenten (Fase G)

Naast de persoonlijke vault kan vertrouwelijk materiaal (bijv. per organisatie/commissie/klant/scope) in **gescheiden compartimenten** worden verwerkt, volgens een **need-to-know lattice** (Bell–LaPadula "no write-down"):

- **Persoonlijk (LAAG) → compartiment (HOOG)** is toegestaan; uit een compartiment stroomt **niets** terug naar persoonlijk. De scheiding is **structureel** (fysiek gescheiden olw-vaults, geen code-pad), niet policy-based.
- Elk compartiment is een **zelfstandige olw-workspace-vault** (`raw/`, `wiki/`, `authoring/`, `.obsidian/`, `wiki.toml`, `.olw/`), **buiten de git-repo** (`~/Confidential/<naam>/`, mode 700), platte tekst — FileVault + Laag-1-afsluiten dekken data-at-rest.

**Scripts (`.claude/`):**
- `new-compartment.py <naam>` — richt een compartiment-workspace-vault in.
- `confidential-triage.py {scan|move}` — de inkomende classificatie-stap (personal LAAG → compartiment HOOG). `scan` (read-only) vlagt persoonlijke notities tegen een lokale seed-config (per compartiment zoektermen: naam/aliassen/personen/codenamen) en schrijft een lokaal vlag-rapport; `move` (dry-run default, `--apply` voert uit) verplaatst bevestigde notities + gerefereerde bijlagen naar `~/Confidential/<naam>/authoring/notes/` met behoud van mapstructuur + omkeerbaar move-manifest. Seed-config + rapport zijn zelf vertrouwelijk → lokaal/gitignored; alleen JSON-status naar Claude (privacy-grens). Zie het sjabloon `.claude/_triage-seeds.example.toml`.
- `sync-personal-context.py <naam>` — kopieert gepubliceerde persoonlijke wiki-kennis naar `raw/_personal-context/` (gemarkeerd), zodat olw-synthese in het compartiment die kennis meeweegt.
- `sync-personal-wiki-ref.py <naam>` — APFS-kloont persoonlijke concepten read-only naar `wiki/_personal/` zodat Obsidian-`[[links]]`/backlinks binnen het compartiment resolveren.
- `declassify-to-personal.py --note <pad> --confirm-desensitized` — de **enige** neerwaartse klep: promoveert een bewust ontgevoeligd, algemeen inzicht naar de persoonlijke `raw/notes/` (dubbele bevestiging + provenance-strip; menselijk oordeel dragend).
- `compartment-serve.py <naam>` — iPad thin-client: read-only viewer + draft-review over het **Tailnet** (bindt op het Tailnet-IP, nooit Funnel).

**Principes:**
- **Privacy-grens (As B):** vertrouwelijke inhoud komt nooit als tool-output in Claude's context; alle olw-operaties via lokale subagents. De agent-grens voor *authoring* is nog open — vertrouwelijk schrijven vereist t.z.t. lokale agents.
- **Backup:** opt-in per compartiment (`.backup-enabled`) naar een aparte, E2E-versleutelde Proton-locatie (`~/bin/compartment-backup.sh`); niet naar de lokale mirror tot die schijf versleuteld is.
- **Toegang:** Obsidian alleen op de Mac; op iPad/iPhone uitsluitend via de thin-client (gerenderde HTML); compartimenten worden nooit naar mobiel gesynct.

De per-compartiment guardrails staan in elk `~/Confidential/<naam>/_COMPARTMENT.md`.

## Architectuurprincipes (niet onderhandelbaar)

- **Privacy-grens**: source content (volledige tekst van papers, podcasts, video's) gaat NOOIT naar de Anthropic API. Alleen JSON status-objecten en metadata mogen Claude Code bereiken vanuit de subagents.
- **Systeem vs. instance**: deze repo is **publiek** en bevat het *systeem* — code, tests, mapstructuur, configuratiesjablonen, documentatie. Alles wat van deze specifieke vault is (broninhoud in `raw/`, gegenereerde pagina's in `wiki/`, persoonlijke domeinoordelen in `vault/canon/`, runtime-state, logs) is *instance* en blijft buiten git. Bij twijfel: instance — een publieke push is niet terug te draaien, een gitignore-regel wel. **Gitignore en backup zijn ontkoppeld**: `~/bin/proton-backup.sh` synct expliciete paden, niet "alles wat niet in git zit", dus elke nieuwe gitignore-regel voor instance-data vereist een bijbehorende `rclone sync`-regel — anders valt het in geen enkele backuplaag. De zichtbaarheidstoets staat als stap 2b in `.claude/skills/wrap-up/SKILL.md`.
- **Subagent-patroon**: `build-zotero-bundle.py`, `promote-to-raw.py` en **olw** (ingest/compile/review) worden aangeroepen als lokale (sub)processen die alleen JSON-status of tellingen teruggeven. `summarize_item.py` (fase-2-previews) volgt hetzelfde patroon. Claude Code stuurt ze aan maar voert zelf geen inhoudsverwerking uit — draai-uitvoer van olw altijd naar een log, lees alleen exit-code/tellingen, nooit draft-/conceptinhoud.
- **olw-model**: olw (concept-extractie + synthese) draait op `mistral-small:22b` (fast=heavy) via de vault-lokale `wiki.toml`; `olw review`/`olw compare`/`olw lint` zijn de kwaliteits-backstops. Zie de vault-`CLAUDE.md`-projectdocumentatie voor scoring en daemons.
- **`--hd` flag**: activeert Claude Sonnet 4.6 in plaats van Qwen3.5:9b. Vereist altijd expliciete bevestiging van de gebruiker vóór verzending naar de API.
- **LLM-backend**: alle AI-scripts (`summarize_item.py`, `attach-transcript.py`, `ollama-generate.py`) ondersteunen twee backends via `--backend ollama|mlx`. Default is `ollama` (localhost:11434). Stel `LLM_BACKEND=mlx` in `ResearchVault/.env` in om alle scripts op de MLX-server (localhost:8080, `mlx-community/Qwen3-8B-4bit`) te laten draaien. Een expliciete `--backend`-vlag wint altijd van de env var. Start MLX-server met: `python3 -m mlx_lm server --model mlx-community/Qwen3-8B-4bit`.
- **Zotero**: de Zotero Web API (`api.zotero.org`) is **niet het standaardgedrag** — alle scripts gebruiken by default de lokale REST API op `localhost:23119`. Web API-aanroepen vinden alleen plaats als `ZOTERO_ACCESS=web` expliciet is ingesteld. Modus via omgevingsvariabele `ZOTERO_ACCESS`: `local` (default) — localhost:23119, vereist Zotero desktop, geen authenticatie; `auto` — start Zotero als het niet draait (max 60s, anders exit 1), dan local API; `web` — api.zotero.org, headless-safe, vereist `ZOTERO_API_KEY` uit `vault/.env`. Rationale per context: nachtelijke-taken gebruikt `web` omdat de Mac headless opstart (geen GUI-sessie, Zotero kan niet worden gestart); overdagtaken gebruikt `auto` omdat de gebruiker ingelogd is; interactieve sessies gebruiken de default `local`. Alle Zotero-aanroepen lopen via `.claude/zotero_api.py`. Geen andere cloud-diensten.
- **Ontwikkelsessies**: ook tijdens het schrijven of testen van nieuwe scripts gelden dezelfde privacyregels. Test nooit met echte paper-inhoud als die inhoud als tool-output in Claude's context kan komen. Gebruik synthetische testdata of alleen metadata bij ontwikkeling en debugging.

## Privacyregel: broninhoud blijft lokaal

**Noch de volledige tekst van bronnen (papers, artikelen, transcripten), noch enige door het model gegenereerde tekst op basis daarvan (samenvattingen, parafrases, afgeleide tekst) mag ooit als output van een Bash-commando in Claude's context terechtkomen.** Zodra tekst als tool-output terugkomt, is hij naar de Anthropic API gegaan — ook als de intentie was om hem alleen lokaal te verwerken.

Correcte aanpak voor het verwerken van een bron: bouw eerst de canonieke bundle met `.claude/build-zotero-bundle.py` (privacy-preserving — alleen JSON-status):

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py --item-key ITEMKEY
# → {"status": "ok", "path": "vault/raw/{citekey}__{itemKey}.md"}
```

Voor eigen denkwerk: `.claude/promote-to-raw.py --note <pad>` → `raw/notes/` (zelfde JSON-only patroon). Beide roepen intern `fetch-fulltext.py` / olw aan; geen bron-inhoud bereikt Claude Code als tool-output. De wiki-draft ontstaat daarna via `olw compile` (draai-uitvoer naar een log, nooit conceptinhoud tonen) en de menselijke `olw review`-gate.

De oude `process_item.py`→`literature/`-tak is verwijderd (Fase F): bronnen lopen uitsluitend via `build-zotero-bundle.py` → `raw/` → olw.

Correcte aanpak voor compacte samenvattingen (fase 2, 📖-items): gebruik `.claude/summarize_item.py`. Zelfde privacy-patroon: de samenvatting wordt naar een lokaal bestand geschreven; alleen het pad wordt teruggegeven:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY \
  --type paper|youtube|podcast \
  --title "Titel" --authors "Achternaam, V." --year 2024
# → {"status": "ok", "path": ".cache/_summary_ITEMKEY.md"}
```

Claude Code toont het pad; de gebruiker leest het bestand en geeft Go of No-go.

Voor losse stappen of speciale gevallen (transcripten, snapshots): gebruik `.claude/fetch-fulltext.py` direct:

```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/fetch-fulltext.py ITEMKEY .cache/bestand.txt
```

**Snapshot-schoonmaak:** bij HTML-snapshots (linked_file én storage) haalt `fetch-fulltext.py` alleen de hoofd-artikeltekst eruit via **trafilatura** (`extract_article_text()`) — nav/ads/comments/boilerplate worden weggelaten (volledige-pagina-snapshots van bijv. Tweakers gingen zo van ~170KB naar ~5KB, wat een trage/afgekapte `olw ingest` voorkomt en de concept-extractie schoon houdt). Bij ontbrekende trafilatura of lege extractie valt het terug op de oude naïeve tag-strip. `trafilatura` moet in de zotero-mcp-venv staan (`bin/python3 -m pip install trafilatura`); pin het t.z.t. in de uv-tool-spec zodat een venv-rebuild het niet verliest.

Daarna verwerken via lokale LLM:
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input .cache/bestand.txt --output raw/notes/bestand.md --prompt "..." [--backend ollama|mlx]
```

Dit geldt ook voor snapshot-HTML, VTT-transcripten en podcast-transcripten: nooit `cat` of `print` op de volledige inhoud uitvoeren als Bash-tool.

## Actieve skills
- Lees en volg `.claude/skills/SKILL.md` bij elke research-sessie.
- `.claude/skills/wrap-up/SKILL.md` — activeer bij "update github" of `/wrap-up`.
- `.claude/skills/model-evaluatie/SKILL.md` — activeer bij "model bake-off", "welk model voor olw", "modellen vergelijken" of `/model-evaluatie`. Protocol in rondes met de metrieken en hun valkuilen; afgeleid uit de bake-off van 14–16 aug 2026 (ADR-0004). Het openstaande meetwerk staat in `ResearchVault-plans/plans/olw-config-optimalisatie.md`.