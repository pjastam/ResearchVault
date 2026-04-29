# Changelog

## v1.15 — 29 april 2026

### 📡 FreshRSS & NetNewsWire integratie

- FreshRSS actualize omgezet van SSH+`docker exec` naar HTTP curl-aanroep (Protection Mode op HA SSH add-on staat nu aan)
- Deduplicatiefilter toegevoegd: items die al in Zotero staan worden niet meer getoond in de HTML-lezer
- HTML-lezer verwijderd uit FreshRSS-context (NNW via Atom-feeds is leidend geworden)
- FreshRSS/NNW/Tailscale workflow gedocumenteerd in CLAUDE.md

### 🎙️ Feedreader: podcast-support en leerloop

- Podcast-support toegevoegd: show notes worden gescoord en gecachet; podcast-items verschijnen in `filtered-podcast.xml`
- Titelmatching toegevoegd als tweede pass in `feedreader-learn.py`: Zotero-titels worden vergeleken met logboek-entries ook zonder URL-match
- nature.com RSS-feed toegevoegd aan `feedreader-list.txt`
- Dubbele skip-registratie in feedreader-server opgelost

### 📹 YouTube transcript attachment pipeline

- `attach-transcript.py` toegevoegd: haalt transcript op, genereert cleaned versie + abstract via Qwen, slaat op als bijlage in Zotero
- Ingest-procedure uitgebreid met transcript-stap vóór Go/No-go
- Notitiestructuur voor video/podcast gedocumenteerd (geen `## Relevant quotes`; tijdcodes onbetrouwbaar)

### ⚙️ Launchd-structuur

- `feedreader-server` en `ttyd` omgezet van LaunchAgent naar LaunchDaemon (draaien nu als root, ongeacht ingelogde gebruiker)
- `pmset` wake vervroegd naar 05:30; race condition met UserEventAgent gedocumenteerd
- rclone TCC-vereiste gedocumenteerd (Full Disk Access nodig voor headless runs)
- Shutdown-guard: 21:00-run sluit Mac alleen af als geen gebruiker ingelogd is

### 🧹 Overige

- `pure_cache/` en `read_queue.jsonl` toegevoegd aan `.gitignore`
- Vault opgeschoond: `craft/`-map verwijderd

---

## v1.14 — 8 april 2026

### 🔄 Automatische Zotero database-update

- Nieuwe launchd-agent `nl.researchvault.zotero-update` draait dagelijks om 05:45 en voert `zotero-mcp update-db --fulltext` uit vóór de feedreader-score run om 06:00
- De semantische zoekdatabase is daardoor altijd actueel bij het starten van een sessie — geen handmatige update meer nodig

### 📡 Atom-feeds: leeftijdsfilter en itemlimiet

- `feedreader-score.py` filtert items ouder dan **30 dagen** (webartikelen, podcasts, YouTube) of **365 dagen** (academische feeds) uit de Atom-feeds
- Elke Atom-feed is beperkt tot maximaal **300 items** (top-N op score)

### 🔢 Sortering op score in NetNewsWire

- Items in de Atom-feeds krijgen een synthetische publicatietijd binnen de huidige dag (hogere score = later tijdstip), zodat NetNewsWire met **Newest First** altijd op relevantiescore sorteert
- `feedreader-server.py` retourneert nu altijd **HTTP 200** voor feed-verzoeken (nooit 304 Not Modified), zodat NetNewsWire de feed bij elke poll echt ververst

---

## v1.13 — april 2026

### 🆕 Feedreader: hernoemd en uitgebreid

- Alle `phase0-*` bestanden hernoemd naar `feedreader-*` door de hele codebase
- Workflow vereenvoudigd van 4-fasen naar **3-fasen model**: Breed vangen · Filteren · Verwerken & opslaan
- YouTube- en podcast-feeds toegevoegd naast webartikelen
- Automatische **brontype-detectie**: webartikelen (📄), YouTube (▶️), podcasts (🎙️)
- **Type-filterknoppen** in de HTML-lezer: Alles / 📄 / ▶️ / 🎙️
- **Twee-paneel HTML-lezer** met sortering op datum, tooltips en publicatiedatum per item
- `feedreader_core.py` toegevoegd: gedeelde functies (`cosine_similarity`, `compute_weighted_profile`, `score_label`, `detect_source_type`) en drempelconstanten

### 🔒 Privacy-architectuur: volledig lokale verwerking

- **Lokale Ollama-pipeline** ingevoerd: broninhoud verlaat de Mac mini nooit voor generatietaken
  - `fetch-fulltext.py` — haalt volledige tekst op uit Zotero (PDF, snapshot, VTT, transcript)
  - `ollama-generate.py` — genereert gestructureerde notes via Qwen3.5:9b (256K contextvenster)
- **`process_item.py`** — privacy-preserving subagent voor literatuurnotities; Claude Code ontvangt alleen een JSON-statusobject, geen bron-inhoud
- **`summarize_item.py`** — compacte samenvattingen voor fase 2 (📖-items); ook alleen pad als output
- Privacyregel gedocumenteerd in CLAUDE.md: geen bron-inhoud als Bash-output in Claude-context

### 📥 Zotero-integratie: actieknoppen en hulpscripts

- **✅ en 📖 actieknoppen** in de HTML-lezer en Atom-feeds; direct gekoppeld aan de Zotero Web API
  - ✅ = item markeren als direct verwerken (met `✅`-tag in Zotero)
  - 📖 = item markeren als samenvatting nodig (met `📖`-tag in Zotero)
- `zotero-inbox.py` — voegt items toe aan Zotero `_inbox` collectie via de web API
- `zotero-remove-from-inbox.py` — verwijdert items na verwerking
- `zotero_utils.py` — gedeelde hulpfuncties (API-sleutel, collectie-ID)
- `ZOTERO_API_KEY` uitgelezen uit `~/.zprofile` — geen hardcoded keys meer in scripts
- **`status`-veld** toegevoegd aan YAML frontmatter (`unread`/`read`), afgeleid van Zotero-tag `✅`
- YAML frontmatter-bug opgelost: tags zonder `#` in frontmatter-arrays (Obsidian parse-fix)

### 📡 Atom-feeds voor NetNewsWire

- Drie **type-specifieke Atom-feeds** aangemaakt:
  - `filtered-webpage.xml` — webartikelen (hernoemd van `filtered-web.xml`)
  - `filtered-youtube.xml` — YouTube-video's
  - `filtered-podcast.xml` — podcast-afleveringen
- **Actieknoppen (✅/📖)** gesynchroniseerd in de Atom `<content>` voor gebruik in NetNewsWire
- Originele bronnaam weergegeven als auteur per Atom-entry
- Gedeelde `make_item_summary` functie voor HTML-lezer en Atom-feeds (DRY)

### 🎙️ Podcast- en YouTube-artikelen via Ollama

- **Artikelgeneratie** voor YouTube en podcast-afleveringen via Ollama `qwen2.5:7b` (asynchroon, met laadpagina die herlaadt)
- Gegenereerde artikelen gecachet in `article_cache/`
- **`abstract`-injectie**: na artikelgeneratie wordt de volledige tekst ook opgeslagen als `abstract`-veld in het transcript-cache JSON-bestand
- Podcast-artikelen worden alleen aangemaakt bij show notes ≥ 200 tekens (`SHOWNOTES_MIN_LENGTH`)

### 💻 Browser-terminal (ttyd)

- **`ttyd` browser-terminal** als iframe in de HTML-lezer (poort 7681, `--writable`)
- **⌨️ terminal**-knop in de header van de HTML-lezer opent de terminal in een iframe
- iframe-URL gebaseerd op `window.location.hostname` zodat de terminal ook werkt op iPad via het LAN-IP van de Mac mini
- Launchd-agent `nl.researchvault.ttyd` toegevoegd voor permanente beschikbaarheid

### 🧠 Leerloop (feedreader-learn.py)

- **Drie signaalcategorieën** onderscheiden: ✅ positieven (toegevoegd aan Zotero) · 👎 expliciet afgewezen · ❌ zwak negatief (niet toegevoegd na timeout)
- Skip-queue (👎) wordt verwerkt vóór Zotero-matching
- **Drempeladvies** verschijnt na ≥ 30 positieven; daarna continu bijleren
- Drempels `THRESHOLD_GREEN` en `THRESHOLD_YELLOW` aanpasbaar in `feedreader-score.py`

### 🔧 Overige verbeteringen

- `index-score.py` — relevantiescore voor Zotero `_inbox` items (ChromaDB, all-MiniLM-L6-v2, gewicht 3 voor items met PDF-annotaties)
- Race condition in `feedreader-server.py` opgelost; kapotte cache-cleanup hersteld
- Actieknoppen omgezet van `fetch()` naar image-trick om CORS-problemen te vermijden
- Diverse codereviews en codekwaliteitsverbeteringen (`feedreader-server.py`, `summarize_item.py`)
- Versienummers verwijderd uit bestandsnamen (installatiegidsen e.d.)
- Inline commentaar-bug in `feedreader-list.txt` opgelost (trailing spaces veroorzaakten parse-fout)

---

## v1.12 — eerste publieke release

Basis feedreader-infrastructuur (destijds Phase 0), Zotero MCP-integratie, Obsidian vault-structuur en 3-fasen researchworkflow.
