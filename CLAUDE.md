# CLAUDE.md — Werkwijze ResearchVault

> **Bevroren specificatie.** Pas dit bestand alleen aan na expliciete beslissing. Elke wijziging verandert het gedrag van alle toekomstige ingests en lint-runs.

## Gedragsregels voor Claude Code

- **Stel eerst vragen, neem niets aan.** Bij probleemanalyse en diagnose: stel gerichte vragen vóór je oorzaken of oplossingen formuleert. Werk iteratief: één hypothese tegelijk toetsen. Neem nooit situationele feiten aan (Ollama bereikbaar, Zotero draait, scriptpad klopt, config correct) zonder die eerst te verifiëren.
- **Plan eerst, voer pas uit na goedkeuring.** Presenteer bij elke voorgestelde wijziging (scripts, configuratie, bestanden) eerst het plan. Stel vragen als er keuzes te maken zijn. Voer pas iets door na expliciet akkoord.
- **Eén hypothese tegelijk.** Bij bugs of onverwacht gedrag: toets één oorzaak per stap. Maak niet meerdere wijzigingen tegelijk — dat maakt de oorzaak onherleidbaar.
- **"Update github" = wrap-up eerst.** Wanneer de gebruiker vraagt om naar GitHub te pushen ("update github", "push naar github", "commit en push" of soortgelijk), activeer dan altijd eerst de workspace-brede skill `~/.claude/skills/wrap-up/SKILL.md` vóórdat je git-commando's uitvoert. (Stond tot 30 aug 2026 in deze repo; verhuisd naar workspace-niveau omdat een sessie die niet vanuit deze repo start hem anders niet laadt.)

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

**De guard geldt voor élk brontype, en de hint vertakt daarop (sinds 22 aug 2026).** De melding
stamde uit het PDF-geval en stuurde daarom altijd naar de Zotero-index en OCR. Op 22 aug 2026
strandden vier blogposts van Skipr en Zorgvisie op deze status — items met een HTML-snapshot en
nergens een PDF, dus de diagnose wees naar een index en een OCR-stap die voor die items niet
bestaan. Een melding die naar de verkeerde plek wijst kost méér tijd dan geen melding, want je
gaat wél zoeken. `_leegte_hint()` leest nu het `source_type` uit de frontmatter van de zojuist
geschreven bundle en kiest daarop: `paper` → index/OCR; `web` → open `~/Zotero/Snapshots/{key}.html`
(cookiemuur, paywall, of tekst die pas via JavaScript laadt); `youtube`/`podcast` → eerst
`attach-transcript.py` draaien; onbekend → neutrale melding. Elke variant eindigt op "Niet
ingesten". Tests: `test_build_zotero_bundle.py`.

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
- Het script vergelijkt de embeddings van inbox-items met het gewogen gemiddelde van je bestaande bibliotheek (via ChromaDB, model: `nomic-embed-text-v2-moe` via Ollama, 768 dim — sinds 23 aug 2026, ADR-0007; daarvóór `all-MiniLM-L6-v2`, 384 dim). `index-score.py` leest **beide** zijden uit ChromaDB en draagt dus geen eigen embedder
- Items met PDF-annotaties in Zotero wegen zwaarder mee in het voorkeursprofiel (gewicht 3 vs. 1)
- Uitvoeren: `~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py`
- Output: gesorteerde lijst met scores 0–100, labels 🟢 (≥70) · 🟡 (40–69) · 🔴 (<40)

## Zotero-hulpscripts
- `.claude/zotero-inbox.py` — leest alle items uit de Zotero `_inbox` collectie via de lokale REST API (localhost:23119); gebruik voor overzicht of scripting: `python3 zotero-inbox.py --json`; vereist dat Zotero draait
- `.claude/zotero-remove-from-inbox.py` — verwijdert een item uit de `_inbox` na verwerking via `zotero_api.py` (default: local API, vereist Zotero desktop):
  ```bash
  ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
  ```
- `.claude/zotero_utils.py` — gedeelde SQLite-hulpfuncties voor feedreader-score.py, feedreader-learn.py en index-score.py; leest items en gewichten direct uit de Zotero-database (geen API-aanroepen).

  **`WEIGHT_DEFAULT` en `WEIGHT_ANNOTATIONS` zijn een paar absolute gewichten, geen basis plus opslag**
  (besluit 23 aug 2026). Een geannoteerd item weegt dus 3, niet 4. Tot die datum deed
  `get_library_keys_with_weights()` `+=`, waardoor het 4 werd — terwijl de constante in
  `feedreader_core.py` zichzelf becommentarieert als "3x weight vs. unannotated", haar naam de
  tegenhanger is van `WEIGHT_DEFAULT`, en deze CLAUDE.md "gewicht 3 vs. 1" zei. Vier van de zes
  signalen zeiden 3; alleen de docstring en de uitvoerende regel zeiden 4. De tegenspraak zat al in
  `bcf6736` (24 mrt 2026), de commit die de constante introduceerde: er is nooit een refactor geweest
  die de betekenis verschoof, hij is zo geboren en heeft vijf maanden ongezien bestaan omdat er geen
  test op dit bestand stond. Gemeten effect op de rangschikking: **geen** — in ronde 1 van de
  embedding-bake-off was de ongewogen variant niet te onderscheiden van de gewogen (alle
  95%-intervallen overlapten volledig).

  **Annotaties zitten bewust wél in de sleutelverzameling.** `annotation` is in Zotero een eigen
  itemtype en passeert het `note`/`attachment`-filter; 58% van de 9.405 sleutels is zo'n losse
  PDF-markering van mediaan 17 tekens. Dat ziet eruit als een lek, maar weghalen levert niets op:
  het zijn de passages die jij zelf markeerde. Verander het niet zonder opnieuw te meten.

  **Sinds 23 aug 2026 staan ze niet meer in ChromaDB, en dat is geen keuze geweest.** De
  sleutelverzameling hierboven is ongewijzigd, maar `get_embeddings_for_keys()` vindt er nog
  maar 42% van terug: de herbouw die ADR-0007 nodig had loopt via
  `zotero-mcp update-db --fulltext`, en die route leest de Zotero-SQLite met
  `WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')` (`local_db.py:743`, `:826`).
  De API-route — `update-db` zónder `--fulltext` — filtert alleen `attachment`/`note` en laat
  annotaties er wél door; zo is de oude collectie van 9.558 documenten ooit gevuld, en de
  nachtelijke `--fulltext`-runs hebben ze daarna nooit verwijderd maar ook nooit aangevuld.
  Gemeten op de wisseldag: profiel-dekking van **9.365 van 9.405 sleutels (99,6%) naar 3.951
  (42,0%)**; de 278 sleutels met gewicht 3 bleven volledig behouden, verloren zijn 5.414
  markeringen van gewicht 1. Ronde 1 van de bake-off mat "annotaties eruit" op mediane rang
  1.618 tegen 1.465 voor de productievorm, met volledig overlappende 95%-intervallen — dus
  geen meetbare schade, maar het is wél een **tweede gelijktijdige verandering** naast de
  modelwissel. Wie de uitkomst van fase 4 (`THRESHOLD_STAR`) duidt, heeft daarmee twee
  oorzaken in plaats van één.
  Tests: `test_zotero_utils.py` (7 stuks, kale stdlib — `numpy` wordt gestubd omdat
  `feedreader_core` het op modulehoogte importeert maar alleen binnen functies gebruikt).
  **Die stub werkt alleen doordat `feedreader_core` sinds 28 aug 2026 `from __future__ import
  annotations` draagt.** Zonder die regel evalueert Python ≤3.13 de annotatie `np.ndarray` bij
  het inlezen van de module en klapt de import eruit op de lege stub; Python 3.14 doet dat uit
  zichzelf al niet meer (PEP 649). De CI stond op 3.11 en was daardoor vijf dagen rood terwijl
  de suite op de 3.14-ontwikkelmachine groen bleef — een klasse fouten die lokaal principieel
  onzichtbaar is. De workflow draait nu een matrix over 3.12 én 3.14, de twee versies die op
  de Mac Mini echt gebruikt worden.
- `.claude/zotero_api.py` — unified Zotero API-client; kiest automatisch local of web op basis van `ZOTERO_ACCESS`; publieke API: `zotero_request(path, method, data, extra_headers)`; laadt vault `.env` voor web-modus credentials
- `.claude/enrich-inbox.py` — batch-verrijking van `_inbox`-items zonder `_enriched`-tag; alle Zotero-aanroepen via `zotero_api.py`. **Modus: `web`, in beide batches** — verrijking *schrijft* (tags, metadata, bijlagen) en de lokale API (:23119) is read-only. Tot 22 aug 2026 stond `nl.pietstam.overdagtaken` op `ZOTERO_ACCESS=auto`; de leeskant werkte, dus de stap zag er gezond uit, maar élke PATCH gaf `HTTP 501 Not Implemented`. Gemeten die dag: de 09:00-run meldde `{"status": "ok", "enriched": 0, "skipped": 140, "errors": [5× 501]}` met exit 0. De vier die ochtend toegevoegde items bleven daardoor onverrijkt en hun Go-bundle strandde op `leeg`. `~/bin/overdagtaken.sh` draait de stap nu expliciet met `env ZOTERO_ACCESS=web`; de plist blijft op `auto` voor de lezende stappen.
  **Exit-code (sinds 22 aug 2026):** 1 bij een *systematische* storing, 0 bij losse per-item-fouten. `systematische_fout()` toetst twee dingen, elk met een ondergrens van 3 fouten zodat één kapot item geen alarm geeft: (1) geen enkele poging slaagde, of (2) één foutsignatuur — de HTTP-status als die er is — dekt minstens de helft van de pogingen. Bij een storing draagt de summary een `systematisch`-veld en is `status` gelijk aan `systematisch-gefaald`, zodat de batchscripts hun eigen WAARSCHUWING-regel loggen. Tests: `test_enrich_inbox.py`.
  Per item: (1) metadata via CrossRef (DOI) of Open Graph (webartikel); (2) bijlage: OA-PDF via Unpaywall, HTML-snapshot, of voor podcast-items met show notes in feedreader-cache: show notes als `abstractNote` + tag `_enriched-shownotes`; VU EZProxy-URL in `extra` als fallback voor paywalled papers

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

**ffmpeg-voorstap (sinds 22 aug 2026).** `_naar_wav()` zet de gedownloade audio eerst om naar 16 kHz mono 16-bit PCM — precies wat whisper.cpp intern toch al wil. Reden: whisper-cli leest audio via de ingebouwde decoders van ggml/dr_libs en is nergens tegen `libav*` gelinkt (`otool -L` bevestigt dat). Die kennen wav, mp3 en flac, maar géén m4a/aac of opus — en bij een onleesbaar bestand meldt whisper-cli `error: failed to read audio file` met **exit 0** en zonder `.txt`, wat niet te onderscheiden is van een mislukte transcriptie. `download_audio()` accepteerde daarentegen wél `m4a|ogg`, dus die twee stonden scheef op elkaar. Gemeten blootstelling: 839 van 840 gecachete afleveringen was mp3, één m4a. De tijdelijke WAV wordt opgeruimd door de functie die hem maakte; de `.txt` niet — die leest de aanroeper nog.

> `brew install ffmpeg` alléén lost dit niet op: whisper-cli start geen ffmpeg-proces. Ontbreekt ffmpeg, dan geeft `_naar_wav()` `None` en krijgt whisper het originele bestand — exact het gedrag van vóór deze stap. ffmpeg is dus een verbetering, geen harde afhankelijkheid.

**Crash in de afbouw ≠ crash tijdens het rekenwerk.** Een non-zero exit betekent niet automatisch dat er niets is. `_draai_whisper()` accepteert de `.txt` alsnog als whisper aantoonbaar tot zijn eind kwam — beide eindmarkeringen (`output_txt: saving output to` én `whisper_print_timings:`) in stderr, én het bestand bestaat. Ontbreekt die evidentie, dan wordt hij afgewezen: een half transcript mag zich niet voordoen als een heel transcript. Aanleiding was item `FNHK8YYX` op 22 aug 2026, waar whisper-cli crashte in `~ggml_metal_device_deleter` tijdens `__cxa_finalize_ranges`, dus ná `exit()`. **Die crash is nooit verklaard** en bleek in isolatie niet reproduceerbaar (dezelfde bron, hetzelfde model, dezelfde taal → exit 0). Dat het onverklaard bleef kwam door de diagnostiek zelf: de melding werd gelogd als `stderr[-500:]`, wat bij een stackdump juist de buitenste frames bewaart en de eigenlijke foutregel weggooit. `_knip()` bewaart nu kop én staart.

> **Privacygrens:** whisper-cli schrijft de transcripttekst naar **stdout** en uitsluitend motordiagnostiek naar **stderr**. Daarom mag stderr in de serverlog en stdout nooit. Wie dit omdraait, doorbreekt de privacygrens.

**De whisper-aanroep woont sinds 28 aug 2026 in `.claude/whisper_local.py`**, losgemaakt uit `attach-transcript.py` zodat gereedschap buiten deze repo kan transcriberen zonder de Zotero-laag mee te slepen (`attach-transcript.py` importeert eruit en gedraagt zich ongewijzigd). De module hangt aan niets anders dan de stdlib — dat is haar bestaansreden. `transcribe_audio()` en `_draai_whisper()` nemen een `formats`-parameter met `("-otxt",)` als default; wie tijdcodes nodig heeft voor sprekerherkenning geeft `("-otxt", "-oj")` mee. `-otxt` moet erbij blijven, want de eindmarkering-controle hangt aan de markering die whisper bij het wegschrijven van de `.txt` afdrukt en dat pad is ook de retourwaarde — zonder die vlag zou de functie bij een geslaagde run stilzwijgend `None` geven, vandaar een `ValueError`.

Tests: `.claude/test_whisper_local.py` — 19 unittests op `_whisper_liep_af()`, `_knip()`, `_naar_wav()` en de `formats`-parameter; draait op kale stdlib (de echte-ffmpeg-test slaat zichzelf over waar `/opt/homebrew/bin/ffmpeg` ontbreekt, zoals op de CI-runner). Heette tot 28 aug 2026 `test_attach_transcript.py`; door de hernoeming vervielen de `importlib`-omweg en de nep-`ZOTERO_API_KEY` die alleen nodig waren omdat het koppelteken in `attach-transcript.py` een gewone import blokkeerde.

**Taaldetectie:** whisper-cli detecteert de taal automatisch op basis van de show notes in de feedreader-cache. Voor Nederlandstalige podcasts wordt `--language nl` automatisch doorgegeven; voor Engelstalige podcasts (Engelse show notes) wordt niets meegegeven (whisper auto-detect). Gebruik `--language` om dit handmatig te overschrijven.

**Tip:** als yt-dlp faalt met "Unsupported URL", voeg de feed toe aan `feedreader-list.txt`; na de volgende feedreader-score.py-run is de directe audio-URL gecachet en werkt de download zonder yt-dlp. Dat is de bedoelde weg: een aflevering hoort via de feedreader binnen te komen, waar hij meteen een `audio_url` én een relevantiescore krijgt. yt-dlp is de nooduitgang voor losse afleveringen van feeds waar je je niet op abonneert — en die tak (`-x --audio-format mp3`) kán niet zonder ffmpeg.

**Let op bij het bijhouden van `feedreader-list.txt`:** `load_feeds()` ontdubbelt niet. Staat een feed twee keer in de lijst, dan wordt hij elke run twee keer opgehaald én telt de dedup-sleutel `(feed_url, canonieke link)` elke aflevering dubbel — waardoor `link_is_shared` aanslaat en de items terugvallen op guid-only. Gemeten 22 aug 2026: de AI Report-feed stond onder twee categorieën en al zijn 135 logregels droegen een guid-identiteit, nooit een URL-vorm.

**Na transcriptie:** verwerk via `build-zotero-bundle.py` → `raw/` → olw (zelfde als papers, zie Ingest-procedure). Het transcript zit als bijlage in het Zotero-item en komt mee in de bundle.

## Feedreader — RSS-filtering (feedreader-score.py)

De feedreader scoort RSS/YouTube/podcast-feeds automatisch op relevantie en produceert drie gefilterde Atom-feeds (webartikel, YouTube, podcast) die via FreshRSS in NetNewsWire binnenkomen. Het is de automatische filterfunctie binnen fase 1 van de workflow. Draait dagelijks via launchd.

**Bestanden:**
- `.claude/feedreader-list.txt` — lijst van feed-URLs (één per regel, `#` = commentaar); bevat webartikel-, YouTube- en podcast-feeds ingedeeld per categorie met `# ── Naam ────` headers
- `.claude/feedreader-score.py` — haalt feeds op, scoort items, detecteert brontype; voor YouTube-items haalt het eerst een transcript op via `youtube_transcript_api` (gecachet in `transcript_cache/`) en gebruikt de transcripttekst voor de scoreberekening; voor podcast-items met show notes ≥ 200 tekens (constante `SHOWNOTES_MIN_LENGTH`) worden de show notes gecachet in `transcript_cache/podcast_{episode_id}.json` (`episode_id` = `podcast_` + MD5-hash van de URL); slaat tevens de directe audio-URL op uit de RSS `<enclosure>`-tag als `audio_url`-veld (gebruikt door `attach-transcript.py` voor directe MP3-download); schrijft de drie Atom-feeds (`filtered-webpage.xml`, `filtered-youtube.xml`, `filtered-podcast.xml`). `generate_html()` is op 18 apr 2026 verwijderd (`3252c4c`); er is geen HTML-lezer meer. De gegenereerde Atom-feeds dragen een channel home-`<link rel="alternate">` naar `{FEEDREADER_PUBLIC_URL}/filtered.html`, waarbij `FEEDREADER_PUBLIC_URL` (de publieke Tailscale-Funnel-basis van de Mini op poort **8443**) uit de omgeving of `~/bin/.researchvault-env` komt — leeg = geen link. Zonder die link slaat FreshRSS geen `htmlUrl` op en raadt NNW de kale poort-443-root (`https://<host>/`), die faalt omdat de funnel alleen op `:8443` luistert (cosmetische "HTML Metadata: TLS error"/"could not connect" in de NNW Activity Log). Sinds 21 aug 2026 draagt elke feed daarnaast een `<link rel="self">` (aanbeveling van de W3C Feed Validator) en een **eigen** `<id>` (`urn:feedreader:filtered-{webpage,youtube,podcast}`) — daarvóór deelden de drie feeds één identiteit, wat een lezer mag opvatten als één feed. Dat is geldige Atom en wordt dus door geen validator gemeld
- `.claude/feedreader_embed.py` — de **itemzijde** van de scoring: `OllamaEmbedder` (een adapter met de `.encode()`-vorm van `SentenceTransformer` rond Ollama's `/api/embed`) en `maak_embedder()`, die het model uit `~/.config/zotero-mcp/config.json` leest. Bestaat sinds 23 aug 2026 (ADR-0007), toen de embedder van `all-MiniLM-L6-v2` naar `nomic-embed-text-v2-moe` ging.

  **Eén modelbron, want het waren er drie.** De ADR sprak van "beide plaatsen" — de config en `feedreader-score.py`. Bij het doorvoeren bleek `backfill-scout.py:467` er een dérde te dragen: `fr.SentenceTransformer("all-MiniLM-L6-v2")`, dat via `importlib` in de namespace van `feedreader-score.py` greep. Alleen de eerste twee omzetten had `/backfill` stil op 384-dim tegen een 768-dim profiel gezet. Alle drie lezen nu dezelfde configuratiesleutel; het model staat nergens meer als constante.

  **De fabriek weigert in plaats van te raden.** Ontbreekt `embedding_config.model_name`, dan valt zotero-mcp terug op `qwen3-embedding` (`chroma_client.py`) — 39× duurder dan de winnaar, met een plausibel ogende maar onvergelijkbare uitslag. `maak_embedder()` werpt dan een `EmbedderConfigFout`, net als bij een niet-`ollama` backend. Gevolg voor de publieke installatie: de RSS-filterlaag vereist nu de Ollama-embeddingbackend (Ollama was daar al vereist voor de artikelgeneratie); zie `docs/src/installation/zotero-mcp.md`.

  **Een storing mag zich niet voordoen als een uitkomst.** `encode()` toetst dat er evenveel vectoren uit komen als er teksten in gingen — anders zou `zip(all_items, embeddings)` in `feedreader-score.py` verschuiven en kreeg elk item de score van een ánder item. Ollama antwoordt bovendien met HTTP 200 en een `error`-veld als het model ontbreekt; dat wordt afgevangen, niet als lege array doorgegeven. Tests: `test_feedreader_embed.py` (19 stuks, kale stdlib, injecteerbare opener)
- `.claude/feedreader_core.py` — gedeelde functies: `cosine_similarity`, `compute_weighted_profile`, `score_label`, `detect_source_type`, `bayesian_score`; constanten: `THRESHOLD_GREEN`, `THRESHOLD_YELLOW`, `THRESHOLD_STAR`, `PRIOR_RELEVANCE`, `WEIGHT_DEFAULT`, `WEIGHT_ANNOTATIONS`. Draagt sinds 28 aug 2026 `from __future__ import annotations`: dit bestand noemt numpy in zijn signaturen terwijl de meeste functies er niet mee rekenen, en `test_zotero_utils.py` leunt daarop met een lege nep-numpy. Zie § Zotero-hulpscripts voor waarom dat vijf dagen alleen in CI zichtbaar was
- `.claude/feedreader_fetch.py` — ophaallaag met eigen HTTP-verzoek, tijdslimiet en herkansing. `fetch_feed()` onderscheidt vier uitkomsten: `ok` (items aanwezig), `leeg` (feed-titel maar geen items — een echt lege feed), `mislukt` (géén titel én géén items, dus de XML is niet geparsed) en `timeout`. Alleen de twee faaltoestanden worden herkanst (`FETCH_RETRIES = 1`, `FETCH_RETRY_DELAY = 2.0`); feeds met een gezette `bozo`-vlag maar bruikbare items gelden als geslaagd. Drie problemen waren de aanleiding:
  1. **Stille netwerkfouten** — `feedparser.parse()` werpt geen exceptie maar geeft een leeg object terug, waardoor mislukte fetches als "0 items" in het log verdwenen, ononderscheidbaar van een feed die niets publiceerde.
  2. **Geen tijdslimiet** — `FEED_TIMEOUT` in `feedreader-score.py` was dode code; feedparser's eigen downloader krijgt er geen mee, dus een server die de verbinding openhield kon de hele scoring-stap laten hangen tot `run_timeout 600` in `nachtelijke-taken.sh` ingreep — waarmee niet één maar álle feeds verloren gingen. Daarom doen we het HTTP-verzoek nu zelf, met expliciete time-out.
  3. **gzip met rommel erachter** — `_maybe_gunzip()` kijkt naar de gzip-magic bytes in plaats van naar `Content-Encoding` (servers liegen daarover) en pakt in twee trappen uit: eerst `gzip.decompress()` (handelt ook aaneengeschakelde leden correct af), en als die weigert omdat er ná de stroom nog bytes staan, een redding via `zlib.decompressobj(31)`. Vastgesteld bij piratenpartij.nl, waar een caching-plugin 220 bytes platte HTML achter de gzip-stroom plakt. Die feed is op 1 aug 2026 uit de lijst gehaald omdat hij dood leek; of déze bug daarvan de oorzaak was, is niet vastgesteld. Let bij zulke diagnoses ook op redirects: `piratenpartij.nl/rss` is een lege 301 naar `/feed/`, dus een client die redirects niet volgt (curl zonder `-L`, of een browser die de body van de redirect aanbiedt als download) ziet een leeg bestand terwijl de feed prima werkt.

  Downloader en parser zijn injecteerbaar en `feedparser` wordt lazy geïmporteerd, zodat `test_feedreader_fetch.py` op kale stdlib draait (CI heeft geen pip-install-stap). **Let op:** `import feedparser` in `feedreader-score.py` is daar niet lokaal in gebruik maar moet blijven staan — `backfill-scout.py` benadert het via `fr.feedparser`
- `.claude/test_feedreader_fetch.py` — unittests voor de ophaallaag (nep-downloader en nep-parser, geen netwerk); draait mee in de `tests`-workflow
- `.claude/feedreader_identity.py` — bepaalt wanneer twee feed-items hetzelfde item zijn. Vier functies: `canonical_url()` strijkt trackingparameters weg, `item_identity()` kiest guid-vóór-link, `item_keys()` levert de sleutelverzameling waarop wordt vergeleken, en `dedupe_by_url()` telt rijen per artikel (gebruikt door `feedreader-learn.py`). Alleen stdlib, zodat de tests op kale stdlib draaien (net als `feedreader_fetch.py`). Aanleiding waren drie los van elkaar staande defecten (gemeten 16 aug 2026 over 13.267 logregels):
  1. **Onstabiele link tussen runs** — de identiteit was de ruwe `entry.link`, en PubMed plakt bij elke fetch `ff=<timestamp>` aan de URL. Daardoor gold hetzelfde artikel elke run als nieuw, kreeg het een nieuwe Atom-`<id>` en verscheen het opnieuw in NetNewsWire. Eén erratum stond 43× in het log — precies het aantal runs sinds 1 aug. Goed voor 502 van de 651 overtollige logregels.
  2. **Geen deduplicatie bínnen een run** — een publicatie in de PURE-feeds van twee co-auteurs (bijv. Cattel én Van Kleef) kwam tweemaal in de output; 69 gevallen. De ruwe URLs zijn daar identiek, dus dit stond los van punt 1.
  3. **Stil verlies bij podcasts** — Captivate/RedCircle geven bij élke aflevering de showpagina als link (`doe-duurzaam.nl/de-groene-nerds-podcast/`, `homeassistant.fm/`). Een URL-sleutel zag aflevering 2 daardoor als duplicaat van aflevering 1 en gooide hem weg.

  **Beleid: denylist, niet allowlist.** Onbekende parameters blijven staan; falen richting duplicaten (zichtbaar) in plaats van richting stil verlies. `TRACKING_PARAMS` bevat alleen wat gemeten is: `ff`/`fc` (PubMed), de UTM-familie, `dgcid` (ScienceDirect, altijd `rss_sd_all`), `af` (Wiley/Health Affairs, altijd `R`), `awCollectionid`/`awEpisodeid` (NPO — redundant, het pad draagt het aflevering-id al), plus `fbclid`/`gclid` preventief. `v` staat **niet** globaal op de lijst maar per host (`TRACKING_PARAMS_PER_HOST`): op PubMed is het een API-versienummer, op YouTube de video-identiteit (277 waarden op één pad `/watch`).

  **Guid vóór link.** De RSS-`<guid>` is op elke gemeten feed minstens zo goed als de link: PubMed `pubmed:42461057` (stabiel), YouTube `yt:video:…`, Captivate een UUID per aflevering, PURE = de link zelf (en beide co-auteurfeeds geven dezelfde guid, dus cross-feed samenvallen blijft werken).

  **`link_is_shared` — de subtiliteit.** Een item draagt twee sleutelvormen: de guid-vorm én de canonieke URL. Die tweede is nodig omdat logregels van vóór 16 aug 2026 alleen URLs kennen; zonder die vorm zou de eerste run na de wissel élk item als nieuw zien — nog een volledige duplicatengolf. Maar bij de podcasts van punt 3 zou de URL-vorm afleveringen laten botsen. Daarom telt `feedreader-score.py` per `(feed, canonieke link)`: komt dezelfde link binnen één feed meer dan één keer voor, dan onderscheidt hij niets en valt dat item terug op alleen de guid. De teller is bewust op *(feed, link)* gesleuteld en niet op de link alleen — zo telt dezelfde publicatie in twee co-auteurfeeds in elke feed als 1 en blijft de URL-vorm daar bruikbaar.
  **Podcast-cachesleutels (sinds 22 aug 2026).** `podcast_cache_id()` en `podcast_cache_ids()` wonen hier ook: de conventie `transcript_cache/podcast_{md5(url)}.json` stond los van elkaar in `feedreader-score.py`, `attach-transcript.py` én `feedreader-server.py`. `podcast_cache_id()` is de sleutel waaronder wórdt weggeschreven (ongewijzigd — geverifieerd dat alle 840 bestaande cache-bestanden identieke sleutels reproduceren); `podcast_cache_ids()` levert de sleutels waaronder mag worden *gevonden*. Er is er meer dan één omdat de URL in het Zotero-item van elders komt dan de link in de feed (share sheet, Connector, podcastspeler) en op precies één as verschilde — het schema:

  ```
  Zotero  http://www.aireport.nl/podcast/s/aireport/de_zomer_waarin_ai…   (item SYQRQ95N)
  cache   https://www.aireport.nl/podcast/s/aireport/de_zomer_waarin_ai…
  ```

  Alles ná het schema was byte-identiek; bij BBC-item `LB3VFDZK` stond het andersom. Van de 840 gecachete afleveringen staan er 60 onder `http`, dus beide richtingen komen voor. **Bewust niet opgelost door `canonical_url()` `http` en `https` te laten samenvallen:** dat is de sleutel waarop `score_log.jsonl` ontdubbelt, waarop de FreshRSS-signalen matchen en waarop de leerloop labelt — hem verruimen laat bestaande identiteiten met terugwerkende kracht samenvallen. De cache is daarentegen wegwerpbaar en een verkeerde treffer kost er niets. Verruim dus de opzoeking, niet de identiteit. Alleen de gemeten as wordt gedekt (denylist-beleid, net als `TRACKING_PARAMS`): geen slash- of www-varianten
- `.claude/test_feedreader_identity.py` — 51 unittests (geen netwerk); de regressietests gebruiken letterlijk de twee erratum-URLs uit `score_log.jsonl` en de twee schema-mismatches uit de cache. Draait mee in de `tests`-workflow
- `.claude/freshrss_utils.py` — GReader API helpers: authenticatie, stream-fetch, auto-sterren; leest credentials uit `~/bin/.researchvault-env`. `freshrss_fetch_stream()` geeft sinds 19 aug 2026 een `StreamResult` met status `ok`/`leeg`/`mislukt`/`timeout`/`afgekapt` — dezelfde vorm als `feedreader_fetch.fetch_feed()`, en om dezelfde reden: `except Exception: return {}` maakte een HTTP 400 ononderscheidbaar van een lege stream, waardoor signaal 3 droogstond.

  **Streams worden volledig uitgelezen** via het GReader-`continuation`-token (`STREAM_PAGE_SIZE = 1000` per verzoek, noodrem `MAX_STREAM_ITEMS = 50_000`). Vóór 19 aug 2026 vroeg de code `?n=1000` en gaf terug wat er kwam; GReader honoreert dat getal letterlijk, dus je kreeg 999 items en dat zag eruit als een compleet antwoord in plaats van als een afkapping. Gemeten: **gesterd 999 van 1.797, reading-list 997 van 2.476, gelezen 57 van 218**. Wordt de noodrem geraakt, dan is de status `afgekapt` en telt die als `failed` — een grens mag zich nooit voordoen als een uitkomst. Een storing op een látere pagina geeft `mislukt` en géén gedeeltelijke data: de labellus zet er negatieven mee, en een half gelezen stream is daar niet te onderscheiden van een hele. Kosten: 1–2 seconden per stream. Zie ADR-0006. `freshrss_read_stream()` leidt de read-state af uit de reading-list (`categories`), want de directe read-stream geeft bij FreshRSS 400. Opener injecteerbaar → `test_freshrss_utils.py` draait op kale stdlib

  **Geheimen blijven uit foutmeldingen (sinds 21 aug 2026).** `maskeer_geheimen()` haalt GReader-auth-tokens (`gebruiker/<40 hex>`), `token=`/`Passwd=`/`password=`-parameters en losse lange hexreeksen uit tekst; `StreamResult.error` draagt daarom een **gemaskeerde melding** in plaats van de rauwe exceptie (die blijft in `_exc` voor lokaal debuggen). Aanleiding: een verkeerd samengestelde URL liet `urllib` de melding `unknown url type: '<gebruiker>/<40 hex>/reader/api/…'` werpen — mét de auth-token — en die belandde als tool-output in een LLM-context. Het env-bestand is gitignored, curl-aanroepen sturen hun uitvoer naar `/dev/null` en de credential-sleutels worden gefilterd; géén van die maatregelen dekt een exceptie die zijn invoer terugecho't. Wie geheimen uit logs en tool-output wil houden, moet dus ook het foutpad afdekken
- `.claude/feedreader-server.py` — lokale HTTP-server (poort 8765); handelt `GET /action?type=skip` af (skip-queue) en serveert Atom-feeds en statische bestanden; genereert leesartikelen via Ollama voor YouTube/podcast; biedt ook de inbox-review REST API (zie URLs hieronder)

  **Transcript-gate en foutrapportage (sinds 22 aug 2026).** De Go-voorstap zat achter `itemType in ("videoRecording", "podcast") or _is_youtube(url)`. Zotero's itemType is echter de keuze van de Connector, niet van de bron: een omny.fm-aflevering komt binnen als `webpage` en glipte erlangs, kreeg geen transcript en strandde op een lege bundle. Derde tak is nu `_heeft_gecachete_audio(url)` — een gecachete `audio_url` is *bewijs* dat er audio is, terwijl een hostnamenlijst stilletjes veroudert; een paper-met-URL krijgt zo'n cache-entry nooit, dus de gate blijft even streng. De opzoeking loopt via `feedreader_identity.podcast_cache_ids()`.

  Daarnaast leest de worker de foutmelding nu uit het juiste veld: `build-zotero-bundle` kent twee faalvormen — `error` (draagt `message`) en `leeg` (draagt `woorden` + `hint`) — en de oude regel las alleen `message`, waarna hij terugviel op stderr of op "onbekende fout". Bij `leeg` wordt de wees-bundle ook verwijderd: hij wordt toch niet ge-ingest, en anders is een lege bundle in `raw/` niet van een echte te onderscheiden. Elke mislukking gaat naar de serverlog, want `_job_status` leeft alleen in het geheugen — na een herstart was er op 22 aug 2026 geen spoor meer van zes leeg-fouten. stderr gaat bewust **niet** in de jobstatus (die wordt via HTTP uitgeleverd en kan brontekstfragmenten dragen), alleen in de log. Tests: `test_feedreader_server.py`

  **Padbeveiliging (sinds 21 aug 2026).** Elke route die zélf een bestandspad samenstelt omzeilt `http.server.SimpleHTTPRequestHandler.translate_path()`, die `..` normaal wegstrijkt. Dat gold voor `_serve_xml` — die bestaat om nooit een 304 te sturen en bouwde daarom een eigen pad — waardoor `GET /../buiten.xml` een bestand buiten `SERVE_DIR` teruggaf. Omdat de server via Tailscale Funnel op poort **8443 aan het publieke internet** hangt, was dat onauthenticated leestoegang tot elk `.xml`-bestand van de gebruiker (gemeten: HTTP 200, lokaal én via de funnel; vault, `~/Confidential` en `~/.ssh` bevatten geen `.xml` en waren dus niet bereikbaar). `veilig_pad()` decodeert nu eerst percent-notatie — anders glipt `%2e%2e/` erlangs — en vergelijkt daarna het **opgeloste** pad met de serveermap, wat ook symlinks naar buiten afvangt. Afwijzing geeft **404 en geen 403**, zodat het antwoord niet verklapt of het bestand bestaat. `_handle_inbox_summary` was al gedekt door `_KEY_RE`; `/article/…` loopt via de basisklasse en is daarmee ook veilig
- `.claude/test_feedreader_server.py` — 18 regressietests: `veilig_pad()` (met letterlijk het pad dat lekte) en `_heeft_gecachete_audio()` (met de omny.fm-URL die de gate miste); laadt het script via `importlib` (hyphen in de naam) en draait op kale stdlib, dus mee in de `tests`-workflow
- `.claude/feedreader-learn.py` — leerloop: verwerkt skip-queue, haalt FreshRSS-signalen op (gestefd/gelezen), matcht Zotero-toevoegingen, geeft drempeladvies (continu proces). De pure labellogica zit in `feedreader_labels.py`; dit script doet de I/O en de coördinatie
- `.claude/feedreader_labels.py` — pure labellogica over logregels, alleen stdlib en dus testbaar (`test_feedreader_labels.py`, inclusief de doc-contracttabel als testgevallen). Vier functies: `apply_skips()` (👎 markeren op identity vóór URL, en melden wat niet matchte), `mark_auto_starred()` (sterren die de pijplijn zichzelf gaf, beoordeeld met de drempel van tóén), `split_positives()` (menselijk oordeel scheiden van zelfbevestiging) en `star_threshold_report()` (de evidentie-tabel voor `THRESHOLD_STAR`). Bestaat omdat `feedreader-learn.py` een hyphen draagt en dus niet importeerbaar is — daardoor was de kern van de leerloop de enige onteste laag van de pijplijn
- `.claude/score_log.jsonl` — groeiend logboek (URL, identity, score, score_raw, bron, source_type, timestamp, star_threshold, prior, embedder, added_to_zotero, skipped, auto_starred). `identity` (sinds 16 aug 2026) is de sleutel waarop volgende runs ontdubbelen; `url` blijft de ruwe link ernaast staan — dat is de link om te openen, en `feedreader-learn.py` matcht daar FreshRSS-signalen op. Oudere regels dragen geen `identity`; `load_existing_log()` canonicaliseert die bij het inlezen alsnog, dus het logboek is niet herschreven. `embedder` (sinds 23 aug 2026) legt vast welk embeddingmodel de score voortbracht: `score_raw` is een ruwe cosine en alleen te duiden binnen het model dat hem berekende, dus het logboek is over de wisseldatum heen niet één reeks. Regels zónder dat veld komen uit `all-MiniLM-L6-v2`. `prior` (sinds 23 aug 2026) legt vast welke `PRIOR_RELEVANCE` gold; regels zónder dat veld zijn niet met één constante te duiden, want de prior wisselde op 2 mei 2026 van 0.70 naar 0.80 — lees zo'n regel dus bij zijn eigen `timestamp`. `star_threshold` (sinds 19 aug 2026) legt vast welke `THRESHOLD_STAR` gold toen de regel werd geschreven, zodat `mark_auto_starred()` een regel beoordeelt met de drempel van tóén. Zonder dat veld zou elke verhoging de betekenis van bestaande regels verschuiven: handmatige sterren in de band [oude drempel, nieuwe drempel) zouden als zelfbevestiging gaan gelden, en die band groeit bij elke volgende verhoging. Bevriezen op één constante lost dat niet op — dan schuift de fout naar de andere kant. Regels zónder het veld dateren van vóór die datum en krijgen `HISTORIC_AUTOSTAR_THRESHOLD = 70`, een waarde die bewust níet meebeweegt
- `/tmp/feedreader-star-queue.txt` — kandidaten voor het auto-sterren, geschreven door `feedreader-score.py` en verwerkt door `feedreader-learn.py`. **Appendt** sinds 19 aug 2026 (was `write_text`) en wordt pas geleegd ná een geslaagde sterractie. Daarvoor gold: draaide score.py twee keer voordat learn.py hem las — bijvoorbeeld nadat de FreshRSS-authenticatie een dag faalde — dan was het bewijs van de eerste ronde weg, en viel de auto-ster-markering terug op de vuistregel. `learn.py` leest de queue buiten het auth-blok en ontdubbelt bij het lezen
- `.claude/skip_queue.jsonl` — wachtrij van expliciet afgewezen items (👎); velden `url`, `identity` (de feed-guid), `title`, `timestamp`. Dagelijks verwerkt door `feedreader-learn.py` → `drain_skip_queue()` + `feedreader_labels.apply_skips()`, die op de identity matcht vóór de URL. Skips die geen logregel raken worden gemeld, niet stil weggegooid
- `.claude/transcript_cache/` — JSON-cache van transcripten en show notes; YouTube: `{video_id}.json`; podcast: `podcast_{episode_id}.json`; na artikelgeneratie bevat het cache-bestand ook een `abstract`-veld met de volledige artikeltekst
- `.claude/article_cache/` — HTML-cache van gegenereerde artikelen; YouTube: `{video_id}.html`; podcast: `podcast_{episode_id}.html`
- `~/.local/share/feedreader-serve/` — serveermap (buiten Documents vanwege macOS TCC)

**URLs (lokale HTTP-server op poort 8765):**
- ~~`http://localhost:8765/filtered.html`~~ — **bestaat niet meer.** De HTML-lezer is op 18 apr 2026 verwijderd (`3252c4c`); NNW + FreshRSS namen de leeslaag over. De URL blijft alleen als channel home-`<link>` in de Atom-feeds staan, omdat FreshRSS anders geen `htmlUrl` opslaat
- `http://localhost:8765/filtered-webpage.xml` — Atom-feed webartikelen voor NetNewsWire
- `http://localhost:8765/filtered-youtube.xml` — Atom-feed YouTube voor NetNewsWire
- `http://localhost:8765/filtered-podcast.xml` — Atom-feed podcasts voor NetNewsWire
- `http://localhost:8765/article/{video_id}` — gegenereerd leesartikel voor een YouTube-video (structuur: Inleiding · Kernpunten · Conclusie; taal = originele videotaal)
- `http://localhost:8765/article/podcast/{episode_id}` — gegenereerd leesartikel voor een podcast-aflevering op basis van show notes (zelfde structuur; alleen voor afleveringen met show notes ≥ 200 tekens)
- `http://localhost:8765/inbox` — inbox-review pagina (iPad-vriendelijk): toont Zotero `_inbox`-items gesorteerd op score met Go/No-go knoppen; Go → `build-zotero-bundle.py` → `raw/` + `olw ingest` + verwijder uit `_inbox`; No-go → verwijder direct uit `_inbox`. Bevat tevens een bulk-knop in de header (**✅ Alle ✅-items → Go (N)**) die alle openstaande `✅`-getagde items in één keer via het bestaande per-item `/api/inbox/go`-endpoint queuet (sequentieel, doorgaan-bij-fout; verschijnt alleen bij N>0). De statusbalk toont sinds 22 aug 2026 ook de **foutteksten** (ontdubbeld, want bij een bulk-run is dezelfde oorzaak meestal de helft van de lijst) — daarvóór stond er alleen `❌ N fout` en werd het `error`-veld van de job nergens gerenderd, waardoor een mislukte bulk-Go geen enkele aanwijzing gaf.

  **Let op bij het beoordelen:** de knop filtert de `items`-array die bij het *laden* van de pagina is opgehaald. Tag je op de iPad in Zotero terwijl de pagina al open staat, dan ziet de knop die items niet — herlaad dan eerst. En de `✅`-tag wordt na verwerking niet verwijderd: filter je in de Zotero-app op die tag zónder de `_inbox`-collectie te selecteren, dan zie je de hele historie (22 aug 2026: 708 items met `✅`, waarvan 701 buiten `_inbox`)

**Inbox-review REST API (POST vereist `Content-Type: application/json`):**
- `GET  /api/inbox/items` — gecombineerde score + Zotero metadata per `_inbox`-item (JSON)
- `GET  /api/inbox/jobs` — status van alle achtergrond-jobs (`pending`/`running`/`done`/`error`)
- `GET  /api/inbox/summary/{key}` — leest `.cache/_summary_{key}.md` als die bestaat
- `POST /api/inbox/go` — /research-pariteit: voor `videoRecording`/`podcast`/YouTube-items (gate op `type`, met `url` in body) eerst `attach-transcript.py` (web-modus), dan `build-zotero-bundle.py` + `olw ingest` (asynchroon); vereist `title` in body. Removal na succes via de web-API (de lokale API :23119 is read-only). Faalt de transcript-stap → job `error`, item blijft in `_inbox`
- `POST /api/inbox/nogo` — verwijdert `key` direct uit Zotero `_inbox` (synchroon, web-API)
- `POST /api/inbox/summarize` — start `summarize_item.py` voor `key` (asynchroon)

**Scores en labels:** 🟢 ≥50 · 🟡 40–49 · 🔴 <40 (Bayesiaanse scores met prior π=**0.80**; de ruwe cosine komt sinds 23 aug 2026 uit `nomic-embed-text-v2-moe` (768 dim) in plaats van `all-MiniLM-L6-v2` (384 dim) — zie ADR-0007 en het `embedder`-veld in `score_log.jsonl`; drempels worden bijgesteld via feedreader-learn.py). De prior stond tot 2 mei 2026 op 0.70 en ging toen naar 0.80, gemarkeerd als "tijdelijk voor testdoeleinden" — bevestigd op 23 aug 2026, want `THRESHOLD_STAR = 75` is op 19 aug empirisch geijkt op scores die ónder 0.80 zijn geproduceerd; terugzetten zou die ijking stil ongeldig maken. Het kantelpunt van `bayesian_score()` ligt op `raw = (1−prior)×100`, dus bij raw 20 in plaats van raw 30: onder de oude prior was raw 20 nog 🔴 (37), onder de huidige is het 🟢 (50). Items met score ≥`THRESHOLD_STAR` (sinds 19 aug 2026: **75**, was 70) worden auto-gestefd in FreshRSS/NNW.

**Handmatig uitvoeren:**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-score.py
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

**Leerloop — signaalhi­ërarchie (verwerkingsvolgorde in de labellus):**
1. ⭐ NNW-ster (FreshRSS starred) → positief
2. ✅ Zotero URL-match of titelmatching → positief
3. 📖 NNW gelezen maar niet in Zotero na >1 dag → negatief
4. ❌ Timeout >3 dagen zonder actie → negatief (zwakst onderbouwd)
5. 👎 Skip-knop in NNW → expliciet negatief. **Harde stop sinds 19 aug 2026 (ADR-0005):** een 👎 blokkeert alle latere signalen, ook een handmatig gezette ster. Wordt daarom als eerste getoetst, niet als laatste

**Volgorde ≠ bewijskracht — en de volgorde is op 19 aug 2026 gedeeltelijk omgedraaid.** Dit is de
lijstvolgorde, maar de labellus toetst `skipped` nu vóór alles (nummer 5 dus als eerste): een
expliciete afwijzing blokkeert elk afgeleid signaal. Voor de rest geldt nog steeds dat elke treffer
met `continue` afsluit, dus een eerder signaal verhindert de latere — waardoor signaal 1 signaal 3
vrijwel volledig afdekte (194 van de 215 gelezen items zijn óók gesterd). Dat effect is nu kleiner:
die sterren dragen `auto_starred` en tellen niet als menselijk positief. Naar bewijskracht is de
rangorde ongeveer omgekeerd: 👎 is de enige ondubbelzinnige afwijzing, terwijl
de timeout alleen de *afwezigheid* van handeling vastlegt — "niet gezien" en "niet interessant"
zijn daarin niet te onderscheiden (zo staat het ook in `docs/src/usage/phase1-sources.md`). Vandaag
heeft dat verschil geen gevolg, want negatieven voeden het drempeladvies niet: dat komt uitsluitend
uit de positieven. Zodra negatieven wél gewogen worden, is dit onderscheid het eerste wat telt.

Het drempeladvies is sinds 19 aug 2026 een **evidentie-tabel voor `THRESHOLD_STAR`** — de enige drempel met gevolgen (`THRESHOLD_GREEN`/`YELLOW` kleuren alleen; er wordt niets weggefilterd, alleen `MAX_FEED_ITEMS` begrenst). Per kandidaat-drempel: gesterd, daarvan in Zotero, precisie, dekking en **lift** t.o.v. het basispercentage (2,6%). Maatstaf is de Zotero-match, niet de ster — die mag zichzelf niet beoordelen. De 👎's leveren een **harde vloer** (geen drempel onder de hoogste afgewezen score), de timeout-negatieven blijven eruit en dat wordt gemeld. Aanbeveling = laagste drempel boven de vloer met lift ≥ 2,5× en ≥ 30 treffers; anders géén getal. Zie `feedreader_labels.star_threshold_report()`.

**Signaal 2 stond tot 16 aug 2026 droog.** `get_zotero_urls()` bevroeg `itemAttachments.path` met `LIKE 'http%'`, maar dat veld bevat bestandspaden (`/Users/…`, `storage:…`) — de URL van een item of link-bijlage staat in `itemData` onder veld `url`. De query gaf dus altijd een lege set; het URL-deel van signaal 2 heeft nooit gevuurd. Na de fix: 3.489 canonieke URLs en 161 treffers in het bestaande logboek. Onzichtbaar bleef het doordat titelmatching (de andere helft van signaal 2) het opving en de uitvoerregel `✅ via URL: 0 nieuw gelabeld` er identiek uitziet aan een rustige dag — een dood signaal dat door een buurman wordt opgevangen geeft geen alarm.

Alle vier de URL-vergelijkingen (skip-queue, FreshRSS-ster, FreshRSS-gelezen, Zotero) lopen sindsdien via `canonical_url()`. Voor de FreshRSS-signalen is dat robuustheid en geen reparatie: log en Atom-feed worden in dezelfde run geschreven en dragen dus dezelfde ruwe URL. Een **eenmalige herlabelpas** corrigeert regels die door de dode query als negatief zijn gelabeld terwijl het item wél in Zotero staat (60 stuks); die pas werkt één richting (`False → True`, alleen op een Zotero-URL-treffer), markeert wat hij aanraakt met `relabeled_zotero_url` en is idempotent.

Het drempeladvies telt sinds dezelfde datum **per artikel** in plaats van per logregel (`dedupe_by_url()` uit `feedreader_identity.py`). De link-churn had de dataset opgeblazen met 147 positieven en 414 negatieven — één opgeslagen artikel telde 42× mee, want titelmatching herkende elke kopie. Op het huidige advies heeft dit geen effect (70/72/74 in beide tellingen); het is structurele bescherming.

**Signaal 3 stond droog van 29 apr tot 19 aug 2026; hersteld.** `freshrss_read_urls()` bevroeg de stream `user/-/state/com.google/read`; FreshRSS antwoordt daarop met `HTTP 400 Bad Request`, wat door `except Exception: return {}` een lege set werd — ononderscheidbaar van "je hebt niets gelezen". `freshrss_read_stream()` leidt de read-state nu af uit de `categories` van de reading-list, en de statuscode maakt een storing zichtbaar in plaats van stil. Meting na de fix: **218 gelezen items** (waarvan 57 vóór de paginering-fix van dezelfde avond — de rest zat achter de `n=1000`-grens).

De eerdere inschatting dat repareren "slechts ~6 labels verschuift" is achterhaald door de auto-ster-markering: signaal 1 dekte signaal 3 af doordat 194 van de 215 gelezen items óók gesterd waren, maar die sterren zijn nu als `auto_starred` gemarkeerd en tellen niet als menselijk oordeel. Signaal 3 is daarmee het enige negatieve signaal dat een bewuste handeling vastlegt.

> **Beantwoord op 19 aug 2026 — de leerloop wás circulair.** Van de 1.823 gesterde logregels lag er **1.822 op of boven `THRESHOLD_STAR`**; precies één lag eronder (score 65). De pijplijn sterde dus vrijwel uitsluitend zichzelf, en las dat in dezelfde run terug als positief bewijs. Sinds de markeerpas van die dag dragen die regels `auto_starred: true` en zijn ze uitgesloten uit het drempeladvies. Effect: de basis ging van 1.770 naar **106 positieven van menselijk oordeel**, en het advies van ~70/72/74 naar 12/31/48 — het oude advies duwde richting `THRESHOLD_STAR` zelf. **Handel niet naar 12/31/48**: 106 is een dunne basis en het P10-percentiel is daarop wankel. Zie ADR-0005; plan: `ResearchVault-plans/plans/leerloop-autoster-circulariteit.md` (afgerond).

**launchd-daemons (alle vier in `/Library/LaunchDaemons/`, draaien zonder ingelogde gebruiker):**
- `nl.researchvault.feedreader-server` — HTTP-server permanent actief (poort 8765); log: `~/Library/Logs/feedreader-server.log`
- `nl.pietstam.nachtelijke-taken` — login-getriggerde batchrun (sinds Laag-1, jul 2026; niet meer op een 06:00-timer): `morning-batch.sh` (LaunchAgent) schrijft `~/.cache/morning-trigger` bij je ochtend-login → deze daemon vuurt via `WatchPaths` en draait zotero update-db → enrich-inbox → feedreader-score → freshrss actualize → feedreader-learn; kickstart daarna `nl.pietstam.proton-taken` (proton-backup → time-machine → proton-mirror); aan het eind sluit `idle-shutdown.sh` de Mac af als je weg bent (FileVault vergrendelt zo bij afwezigheid/diefstal). Log: `~/Library/Logs/nachtelijke-taken.log`; rclone heeft **Full Disk Access** nodig (Systeeminstellingen → Privacy en beveiliging → Volledige schijftoegang → `/opt/homebrew/bin/rclone`) — zonder FDA blokkeert macOS TCC de toegang tot `~/Documents` stil tijdens headless runs; **veiligheidsregel: de idle-shutdown-stap sluit alleen echt af als `LAUNCHD_RUN=1` gezet is (door de plist) — handmatig uitvoeren van het script sluit de Mac nooit af**
- `nl.pietstam.overdagtaken` — dagbatchrun op 09:00, 12:00, 15:00, 18:00 en 21:00: stappen 1–5 (zotero update-db → enrich-inbox → feedreader-score → freshrss actualize → feedreader-learn); sluit de Mac alleen af na de 21:00-run én alleen als er geen actieve gebruikerssessie is; log: `~/Library/Logs/overdagtaken.log`
- `nl.researchvault.ttyd` — browser-terminal permanent actief (poort 7681, `--writable`); log: `~/Library/Logs/ttyd.log`

> **FreshRSS-setup (huidige configuratie — Option C):** FreshRSS draait als HA Community Add-on (einschmidt/freshrss, poort 7077) op Home Assistant Green (altijd aan), niet op de Mac Mini. De actualize-stap in `nachtelijke-taken.sh` stuurt een HTTP curl-verzoek naar het HA Green Tailscale IP (poort 7077) — geen `docker exec`. FreshRSS haalt de feeds vervolgens op van de Mac Mini (poort 8765 via Tailscale Funnel). De Mac Mini kan daarna afsluiten; FreshRSS op HA Green blijft de items de rest van de dag serveren. NetNewsWire verbindt via het HA Green Tailscale IP (poort 7077). **`base_url`** is ingesteld op `http://100.113.121.73:7077/` via HA → Instellingen → Apps → FreshRSS → Configuratie → Opties (niet via de FreshRSS web-UI — die is read-only voor deze parameter).

## RSS-feeds
- RSS-feeds worden gefilterd door de feedreader; de Atom-feeds in NetNewsWire (via FreshRSS) tonen items gesorteerd op relevantiescore
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
- **Systeem vs. instance**: deze repo is **publiek** en bevat het *systeem* — code, tests, mapstructuur, configuratiesjablonen, documentatie. Alles wat van deze specifieke vault is (broninhoud in `raw/`, gegenereerde pagina's in `wiki/`, persoonlijke domeinoordelen in `vault/canon/`, runtime-state, logs) is *instance* en blijft buiten git. Bij twijfel: instance — een publieke push is niet terug te draaien, een gitignore-regel wel. **Gitignore en backup zijn ontkoppeld**: `~/bin/proton-backup.sh` synct expliciete paden, niet "alles wat niet in git zit", dus elke nieuwe gitignore-regel voor instance-data vereist een bijbehorende `rclone sync`-regel — anders valt het in geen enkele backuplaag. De zichtbaarheidstoets staat als stap 2b in `~/.claude/skills/wrap-up/SKILL.md`.
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

**Snapshot-schoonmaak:** bij HTML-snapshots (linked_file én storage) haalt `fetch-fulltext.py` alleen de hoofd-artikeltekst eruit via **trafilatura** (`extract_article_text()`) — nav/ads/comments/boilerplate worden weggelaten (volledige-pagina-snapshots van bijv. Tweakers gingen zo van ~170KB naar ~5KB, wat een trage/afgekapte `olw ingest` voorkomt en de concept-extractie schoon houdt). Bij ontbrekende trafilatura, een lege extractie **of een extractie onder de 300 woorden** valt het terug op de oude naïeve tag-strip (`MIN_ARTIKEL_WOORDEN`, gelijk aan `MIN_INHOUD_WOORDEN` in `build-zotero-bundle.py`); van de twee wordt dan de grootste genomen. Tot 22 aug 2026 toetste de terugval op `if extracted and extracted.strip()` — oftewel *bestaat er output*. Dat is geen bruikbaar criterium, want een degeneratieve extractie is niet leeg. Gemeten op vier Skipr/Zorgvisie-artikelen met een volwaardige snapshot (18 `<p>`-tags, `<article>`-elementen, geen JS-shell): trafilatura gaf 58/183/52/239 woorden waar de naïeve strip er 498/587/966/717 vond. Alle vier strandden daardoor op `status: "leeg"`. Over de hele Zotero-snapshotmap (198 stuks) gaan er **56 van afgewezen naar bruikbaar**, blijven er 44 terecht afgewezen en verandert er niets aan de 98 waar trafilatura al voldoende opleverde. Een *absolute* ondergrens en geen verhouding, want trafilatura's bestaansreden is juist dat zijn output veel kleiner is dan de naïeve strip — kleiner is normaal, te klein om een artikel te kúnnen zijn is het signaal. De keuze zit in `_kies_tekst()`, los van de extractie zodat hij zonder trafilatura testbaar is (`test_fetch_fulltext.py`). Let op: die 56 komen binnen mét boilerplate; `olw review` blijft de poort. `trafilatura` moet in de zotero-mcp-venv staan (`bin/python3 -m pip install trafilatura`); pin het t.z.t. in de uv-tool-spec zodat een venv-rebuild het niet verliest.

Daarna verwerken via lokale LLM:
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/ollama-generate.py \
  --input .cache/bestand.txt --output raw/notes/bestand.md --prompt "..." [--backend ollama|mlx]
```

Dit geldt ook voor snapshot-HTML, VTT-transcripten en podcast-transcripten: nooit `cat` of `print` op de volledige inhoud uitvoeren als Bash-tool.

## Actieve skills
- Lees en volg `.claude/skills/SKILL.md` bij elke research-sessie.
- `~/.claude/skills/wrap-up/SKILL.md` — workspace-breed; activeer bij "update github" of `/wrap-up`.
- `.claude/skills/model-evaluatie/SKILL.md` — activeer bij "model bake-off", "welk model voor olw", "modellen vergelijken" of `/model-evaluatie`. Protocol in rondes met de metrieken en hun valkuilen; afgeleid uit de bake-off van 14–16 aug 2026 (ADR-0004). Het openstaande meetwerk staat in `ResearchVault-plans/plans/olw-config-optimalisatie.md`.