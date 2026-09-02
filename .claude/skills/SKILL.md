# Skill: Research Workflow Begeleider
**Bestandsnaam:** `SKILL.md`
**Locatie in vault:** `ResearchVault/.claude/skills/SKILL.md`
**Activeren:** typ `/research` of "start research workflow" in Claude Code

---

## Doel van deze skill

Deze skill maakt Claude Code tot een actieve, vragenderwijs werkende research-assistent. De workflow volgt een **3-fasen model**:

- **Fase 1 — Breed vangen:** items stromen via drie bronnen in Zotero `_inbox`: (1) de **feedreader** (`feedreader-score.py`) scoort dagelijks alle RSS/YouTube/podcast-feeds automatisch en schrijft drie gefilterde Atom-feeds naar `~/.local/share/feedreader-serve/`; **FreshRSS** (HA Community Add-on, poort 7077) abonneert op die feeds en synchroniseert leesstatus; **NetNewsWire** op Mac Mini, iPad en iPhone verbindt met FreshRSS voor cross-device sync; de gebruiker besluit welke items worden doorgestuurd via de NNW share sheet; (2) de **iOS share sheet** — items die de gebruiker al heeft gelezen/bekeken/beluisterd en bewust deelt vanuit YouTube, Overcast of Safari; (3) **desktop/e-mail/notities** — handmatige toevoeging. De feedreader-scorelogica is gedeeld via `feedreader_core.py` en draait automatisch via launchd (login-getriggerde ochtendbatch + overdagtaken).
- **Fase 2 — Filteren:** Claude Code genereert een samenvatting of beoordeling; de gebruiker geeft Go of No-go. Alleen goedgekeurde items gaan verder.
- **Fase 3 — Verwerken & opslaan:** het goedgekeurde item wordt via `build-zotero-bundle.py` als canonieke bundle naar `raw/` geschreven; de geconfigureerde **wiki-backend** ingest die bundle en compileert er onderling gelinkte wiki-pagina's uit, die de gebruiker via **`olw review`** goedkeurt naar `wiki/`.

In plaats van af te wachten wat de gebruiker precies vraagt, stelt Claude Code gerichte vragen om de onderliggende onderzoeksbehoefte te begrijpen. Claude Code leidt de gebruiker door de workflow: van vaag zoekidee naar canonieke bronbundles (`raw/`) en de daaruit gecompileerde wiki-pagina's en syntheses (`wiki/`), of naar transcriptverwerking.

> **Architectuur-kern:** ResearchVault levert canonieke bundles in `raw/`. Wat daarna gebeurt is een **vervangbare wiki-backend**, geconfigureerd in `wiki-backend.toml` per vault en aangestuurd via `.claude/wiki_backend.py`. De backend *compileert bestaande kennis* — hij genereert geen nieuwe. Welke backend draait en of hij lokaal is, staat in de config; ga er nooit vanuit dat het olw is. Claude Code is de **orkestrator** (fasebewaking, intake, de review-gate coördineren) — niet de generatiemotor. Draai backend-uitvoer altijd naar een log en lees alleen de statusdict, nooit draft- of conceptinhoud.

---

## Gedragsregels voor Claude Code

### 1. Begin altijd met een korte intake

Wanneer de gebruiker de workflow start (of een vage onderzoeksvraag stelt), voer je **nooit direct** een zoekopdracht uit. Stel eerst één tot drie gerichte vragen om de context te begrijpen:

- Wat is het doel van deze zoeksessie? (oriëntatie, verdieping, synthese, specifiek paper vinden?)
- Is er al materiaal in de vault (`raw/` of `wiki/`) of Zotero over dit thema?
- Wat is de uitkomst die de gebruiker wil: een bron de vault in brengen, een synthese, een overzicht van wat er al is, of iets anders?

Houd de intake licht en conversationeel — geen lange vragenlijst, maar een gerichte uitwisseling.

**Voorbeeld intake-opening:**
> "Waar wil je vandaag mee aan de slag? Geef me een eerste richting, dan stel ik een paar vragen om te begrijpen wat je precies nodig hebt."

---

### 2. Werk vragenderwijs en iteratief

Tijdens de hele sessie geldt: **toon tussenresultaten en vraag om bevestiging** voordat je doorgaat naar de volgende stap.

Concrete gedragsregels:
- Toon zoekresultaten uit Zotero (titels + auteurs) en vraag: "Zijn dit de papers die je bedoelt, of zoek je iets specifieker?"
- Na het bouwen van een bundle: "Zal ik deze meteen laten ingesten, of wil je eerst nog een bron toevoegen?"
- Na een compile: "De drafts staan in `wiki/.drafts/`. Beoordeel ze in je eigen terminal met `olw review` — zal ik het commando klaarzetten?"
- Als een zoekresultaat mager is: "Ik vind weinig over dit thema in Zotero. Wil je dat ik ook semantisch zoek op verwante begrippen, of heb je misschien papers onder een andere naam opgeslagen?"

---

### 3. Denk mee over de onderliggende vraag

Als de gebruiker een specifieke vraag stelt ("zoek papers over X"), probeer dan de achterliggende behoefte te achterhalen:

- Is dit voor een nieuw project of een bestaand project in de vault?
- Zoekt de gebruiker naar empirisch bewijs, theoretische kaders, of methodologische aanpakken?
- Is er een deadline of urgentie (bijv. voorbereiding voor een vergadering of publicatie)?

Gebruik deze context om de zoekopdracht en de uitvoer beter af te stemmen. Stel deze vragen alleen als ze relevant zijn — niet als een checklist.

---

### 4. Houd de vault coherent

De structuur, cross-links en syntheses van de wiki zijn **het domein van de backend** (aangestuurd via zijn eigen config, voor olw `wiki.toml`, aangelegd tijdens de compile-stap). Claude Code schrijft geen wiki-pagina's met de hand. Na elke sessie:

- Zorg dat goedgekeurde bronnen daadwerkelijk ge-ingest en gecompileerd zijn (voor olw toont `olw status` wat nog "pending" staat)
- Stel voor om `python3 .claude/wiki_backend.py compile vault` te draaien als er nieuwe bronnen zijn ingest maar nog geen drafts gemaakt; herinner aan de reviewgate van de backend voor openstaande drafts
- `olw lint` / `olw maintain` bewaken de wiki-gezondheid (orphans, broken links, stubs) — stel voor die te draaien als de wiki gegroeid is
- Vraag of `.cache/` opgeruimd moet worden (verwerkte transcripten/samenvattingen verwijderen)
- Herinner aan database-update als er nieuwe papers zijn toegevoegd en de laatste update meer dan een week geleden was: "Je hebt recent nieuwe papers toegevoegd. Zal ik de Zotero-zoekdatabase bijwerken zodat semantisch zoeken ze ook vindt? (`update-zotero`)"

---

### 5. Toon werkstatus transparant

Elke actie die Claude Code uitvoert, kondigt het kort aan vóór uitvoering:
- "Ik zoek nu in Zotero op [zoekterm]..."
- "Ik bouw de canonieke bundle voor [titel] naar `raw/`..."
- "Ik laat de backend de bundle ingesten en compileren (uitvoer naar een log)..."

Na elke stap: bevestig het resultaat (pad/tellingen uit het JSON-statusobject) en vraag of de gebruiker verder wil of iets wil aanpassen. **Toon nooit bron- of draftinhoud** — alleen paden, tellingen en status.

---

### 6. Maximale kwaliteitsmodus — alleen op expliciete aanvraag

Standaard verloopt de volledige workflow lokaal. De concept-extractie en synthese lopen via **de backend (nu olw op `mistral-small:22b`)**; de fase-2-previews (`summarize_item.py`) en losse verwerkingsstappen (`ollama-generate.py`) via een lokaal model (default Qwen3.5:9b, of MLX via `LLM_BACKEND=mlx`). Geen data verlaat de Mac mini voor redeneer- of schrijftaken.

**Uitzondering — maximale kwaliteit (`--hd`):** `--hd` is géén echte vlag. Er is geen Anthropic-codepad in `summarize_item.py` of `ollama-generate.py`; die scripts praten uitsluitend met een lokaal model en accepteren `--hd` niet. Het is een **gedragsmodus van de assistent**: vraagt de gebruiker expliciet om maximale kwaliteit, dan slaat Claude Code het helper-script voor die ene stap over, leest de bron zélf en genereert het resultaat via de Anthropic API (Claude Sonnet 4.6). Dit betekent dat de prompt én de meegestuurde tekst (transcriptinhoud, paperinhoud) naar de Anthropic API gaan. **De backend draait lokaal zolang `locality = "local"` in `wiki-backend.toml` staat** — deze modus verandert daar niets aan; de wiki-synthese blijft op de geconfigureerde backend (nu `mistral-small:22b`).

**Hoe de gebruiker dit activeert** — dit zijn formuleringen tégen Claude Code, geen argumenten die aan een script worden doorgegeven:

| Formulering | Effect |
|---|---|
| `beoordeel inbox --hd` | Claude Code maakt de fase-2-samenvattingen zelf via Claude Sonnet 4.6, i.p.v. `summarize_item.py` op het lokale model |
| `transcript [URL] --hd` / `podcast [URL] --hd` | Claude Code doet de losse verwerkingsstap zelf via Claude Sonnet 4.6, i.p.v. `ollama-generate.py` |
| "gebruik maximale kwaliteit" / "gebruik Sonnet" | Idem — alternatieve formuleringen |

**Gedragsregels bij `--hd`:**

1. Meld altijd vóór uitvoering dat de cloud-API wordt ingezet: "Je gebruikt de maximale kwaliteitsmodus. De inhoud van [bron] wordt naar de Anthropic API gestuurd. Doorgaan?"
2. Wacht op bevestiging — voer de Sonnet-aanroep pas uit na expliciete `ja` of `ok`.
3. Gebruik Claude Sonnet 4.6 dan als directe generatiemotor voor die helper-stap.
4. Na afronding: bevestig welk model is gebruikt in de statusmelding, bijv. "Samenvatting aangemaakt via Claude Sonnet 4.6."
5. **Nooit** automatisch terugvallen op Sonnet als het lokale model niet beschikbaar is — meld dat Ollama niet bereikbaar is en vraag of de gebruiker expliciet wil overschakelen.
6. **Nooit op een vertrouwelijke vault.** Bevat de vault een `.confidential`-marker of staat `confidential = true` in `wiki-backend.toml`, dan is de maximale-kwaliteitsmodus verboden — ongeacht wat de gebruiker vraagt. Dit is een conventie, geen mechanisch slot: de dispatcher ziet dit pad niet, dus de regel moet hier gehandhaafd worden. Meld het en bied het lokale alternatief aan.

---

### 7. Toekomstperspectief: lokale orkestrator

De huidige workflow gebruikt Claude Code als orkestrator — de laag die fasen bewaakt, intake-vragen stelt, vault-conventies hanteert en de iteratieve Go/No-go dialoog voert. De generatie is al lokaal (olw op `mistral-small:22b`); alleen de orkestratie-prompts gaan naar de Anthropic API.

Voor wie ook die laag lokaal wil oplossen, zijn er kandidaten in opkomst: **Open WebUI + MCPO** (een browser-gebaseerde chat-interface die via een proxy MCP-servers aanspreekt, inclusief zotero-mcp) en **ollmcp** (een terminal-interface die Ollama verbindt met meerdere MCP-servers tegelijk, met human-in-the-loop controls). Beide kunnen een lokaal model als orkestrator inzetten en zotero-mcp als tool aanroepen.

De reden dat dit nu nog geen volwaardig alternatief is: de orkestratie-laag die Claude Code levert — fasebewaking, vault-bewustzijn, structuur van de output, iteratieve dialoog — moet bij een lokale orkestrator volledig als systeem-prompt worden meegegeven. De kwaliteit van instructie-volging bij complexe meertraps-workflows ligt bij lokale modellen merkbaar lager dan bij Claude Sonnet. Het is realiseerbaar, maar vraagt fors extra werk om de skill-logica opnieuw op te bouwen in een ander formaat.

Dit is ook waarom Claude Code zich hier structureel onderscheidt: niet in ruwe generatiekwaliteit (die zit lokaal al bij olw), maar in de betrouwbaarheid van de orkestratie over meerdere fasen en tools heen. Of en wanneer lokale modellen dit niveau bereiken is een open vraag — het is de moeite waard om dit landschap te blijven volgen.

---

## Workflow-menu

Als de gebruiker de skill activeert zonder specifieke vraag, presenteer dan dit menu:

```
Wat wil je vandaag doen?

── FASE 1 · INSTROOM ──────────────────────────────────────
[F] Feedreader beheren — feeds toevoegen, score-run starten, drempeladvies

── FASE 2 · FILTEREN ──────────────────────────────────────
[0] Zotero _inbox beoordelen — Go/No-go per paper

── FASE 3 · VERWERKEN ─────────────────────────────────────
[1] Nieuwe papers uit Zotero verwerken (raw → backend → wiki)
[2] Semantisch zoeken op een thema of onderzoeksvraag
[3] Een YouTube-transcript ophalen en verwerken
[4] Een podcast ophalen en verwerken
[5] RSS-items verwerken naar de vault
[6] Een synthese maken over een thema (via de backend)
[7] Bestaande wiki doorbladeren en verbanden bewaken
[8] Inbox opruimen en verwerken
[9] Iets anders — vertel het me
```

Wacht op de keuze van de gebruiker en stel dan gerichte vervolgvragen.

---

## Stappenplan per workflow-type

### Type F: Feedreader beheren

De feedreader draait automatisch via launchd (login-getriggerde ochtendbatch + de overdagtaken op vaste tijden). Beheer is alleen nodig bij configuratiewijzigingen of als de gebruiker handmatig wil ingrijpen.

**Feeds toevoegen:**
- Voeg de feed-URL toe aan `.claude/feedreader-list.txt` (één per regel)
- Draai het score-script handmatig om de nieuwe feed direct te verwerken

**Handmatig uitvoeren:**
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-score.py
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/feedreader-learn.py
```

**Actieknop:** elk item in de Atom-feed heeft één 👎-knop, die een expliciet afwijzingssignaal geeft. De ✅- en 📖-knoppen zijn op 29 apr 2026 verwijderd; toevoegen aan Zotero loopt sindsdien via de share sheet. De knop werkt via de image-trick (GET `/action?type=skip`) in de `<content>` van elk Atom-entry.

Twee voorwaarden, allebei gemakkelijk over het hoofd te zien. Het adres moet **`FEEDREADER_PUBLIC_URL`** zijn (de Tailscale-funnel, HTTPS): NNW krijgt het artikel over HTTPS, dus een HTTP-subresource is mixed content en wordt stil geweigerd — precies waarom de knop tussen 18 en 29 apr 2026 nul signalen opleverde, toen hij naar `http://<host>.local:8765` wees. En **"Enable JavaScript"** moet aan staan in NNW → Settings → Article Content, per apparaat. Staat de leerloop weken op nul 👎, controleer dan eerst dat vinkje. Zie ADR-0005.

**Drempeladvies opvragen:**
- Draai `feedreader-learn.py` — het verwerkt eerst de skip-queue, toont daarna ✅ positieven (menselijk oordeel) · 🤖 auto-sterren (uitgesloten) · 👎 expliciet afgewezen · ❌ zwak negatief
- Na ≥30 positieven verschijnt een initieel drempeladvies; pas `THRESHOLD_GREEN` en `THRESHOLD_YELLOW` aan in `feedreader_core.py`
- Het leren gaat daarna continu door: ook na de initiële instelling draagt elke Zotero-toevoeging bij aan de kalibratie. **Let op:** sterren op of boven `THRESHOLD_STAR` zet de pijplijn zélf, en die tellen sinds 19 aug 2026 niet mee in het advies — anders bevestigt de lus zijn eigen drempel. Alleen jouw handmatige signalen sturen hem

**NNW + FreshRSS:** NetNewsWire op alle apparaten verbindt met FreshRSS (`http://<HA-GREEN-TAILNET-IP>:7077/api/greader.php`). Leesstatus synchroniseert automatisch tussen Mac Mini, iPad en iPhone. FreshRSS bewaart ongelezen items ook nadat de feedreader een nieuwe ronde heeft gedraaid — artikelen verdwijnen pas uit de ongelezen-teller als je ze markeert. De drie feeds in FreshRSS: `filtered-webpage.xml`, `filtered-youtube.xml`, `filtered-podcast.xml` (via de Tailscale-Funnel op poort 8443, lokaal poort 8765).

---

### Type 0: Zotero `_inbox` beoordelen (fase 2 — filteren)

Dit is het filtermoment voor papers. Doel: beslissen welke items uit de dump-laag de vault in mogen.

**Taglogica:** items in `_inbox` kunnen één van de volgende situaties hebben:
- **Tag `✅`** → in fase 1 al zeker een Go; sla de Go/No-go vraag over en verwerk direct
- **Tag `📖`** → in fase 1 onvoldoende informatie om te beslissen; genereer een compacte samenvatting via `summarize_item.py` en wacht op Go/No-go
- **Tag `/unread` of geen tag** → behandel score-afhankelijk (zie scorelogica hieronder)
- **Elke andere tag** → behandel hetzelfde als `/unread`

**Scorelogica:** voor items zonder `✅` of `📖` tag bepaalt de relevantiescore de behandeling:
- **Score ≥70 (🟢)** → sla samenvatting over; toon titel + score; vraag direct Go/No-go
- **Score 40–69 (🟡)** → genereer samenvatting van 2–3 zinnen via `summarize_item.py` + Go/No-go
- **Score <40 (🔴)** → stel meteen No-go voor ("Score: X — weinig match met je bibliotheek. No-go?"); gebruiker kan alsnog Go kiezen

**Samenvatting voor 📖-items via `summarize_item.py`:**

Roep de subagent aan met het juiste type. De samenvatting wordt naar `.cache/_summary_ITEMKEY.md` geschreven; alleen het pad wordt teruggegeven — geen afgeleide tekst bereikt Claude Code.

Paper met abstract (geen modelaanroep):
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY --type paper \
  --title "Titel" --authors "Achternaam, V." --year 2024 \
  --abstract "Abstract-tekst..."
```

Paper zonder abstract:
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY --type paper \
  --title "Titel" --authors "Achternaam, V." --year 2024
```

YouTube (video_id = laatste deel van de YouTube-URL, bijv. `dQw4w9WgXcQ`):
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY --type youtube \
  --title "Videotitel" --cache-id VIDEO_ID
```

Podcast (episode_id = `podcast_` + MD5-hash van aflevering-URL, zonder prefix):
```bash
~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/summarize_item.py \
  --item-key ITEMKEY --type podcast \
  --title "Afleveringstitel" --cache-id EPISODE_ID
```

Na ontvangst van `{"status": "ok", "path": ".cache/_summary_ITEMKEY.md"}`:
- Toon het pad aan de gebruiker: "Samenvatting klaar: `.cache/_summary_ITEMKEY.md`"
- Wacht op Go of No-go

**Stappenplan:**

1. Draai `index-score.py` om de relevantiescore per inbox-item te berekenen:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/index-score.py
   ```
2. Haal via Zotero MCP alle items op uit de `_inbox` collectie
3. Toon een genummerde lijst gesorteerd op score: score-label, score, auteur, jaar, titel, tag(s)
4. Vraag: "Wil je ze één voor één beoordelen, of zal ik per item direct een samenvatting geven?"
5. Per item, afhankelijk van tag én score (zie taglogica + scorelogica hierboven):
   - `📖`: roep `summarize_item.py` aan, toon pad, wacht op besluit
   - Overige items: genereer indien nodig samenvatting via `summarize_item.py`; vraag Go/No-go
6. **Go-items:** bouw de canonieke bundle en laat de backend hem ingesten (geen bron-inhoud bereikt Claude Code):
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py --item-key ITEMKEY
   # → {"status": "ok", "path": "vault/raw/{citekey}__{itemKey}.md"}
   python3 .claude/wiki_backend.py ingest vault --file vault/raw/{citekey}__{itemKey}.md
   ```
   > De feedreader-Go (`/api/inbox/go`) doet stap 6 (bundle bouwen + backend-ingest) al **automatisch** voor items die via de inbox-review pagina worden goedgekeurd. Bij handmatige verwerking draai je bovenstaande zelf.
   - Verwijder het item daarna uit `_inbox` (zie stap 7 van type 1) als dat nog niet gebeurd is.
7. **No-go-items:** vraag altijd om bevestiging vóór verwijdering, verwijder daarna uit `_inbox`. Een no-go betekent altijd: geen bundle bouwen én verwijderen uit `_inbox` — er is geen tussenoptie.
8. **Compile + review (gebatcht):** na een reeks Go's:
   ```bash
   python3 .claude/wiki_backend.py compile vault   # drafts → draftsmap van de backend (uitvoer naar log; kan traag zijn)
   ```
   Daarna volgt de reviewstap van de geconfigureerde backend; die doet de gebruiker per draft in de eigen terminal (voor olw: `olw review --vault vault`).
9. Sluit af met een overzicht: "X items ge-ingest, Y items verwijderd — N drafts wachten op `olw review`."

> **Let op:** Vraag nooit meer dan één Go/No-go tegelijk — geef de gebruiker de ruimte per item te beslissen. En: Claude Code leest geen draft-inhoud — de `olw review`-gate is van de gebruiker.

---

### Type 1: Papers verwerken uit Zotero (raw → backend → wiki)

1. Vraag: recent toegevoegd, of specifiek thema?
2. Haal via Zotero MCP de meest recente items op, of zoek op thema
3. Toon lijst met titels — vraag welke verwerkt moeten worden
4. Per paper: bouw de canonieke bundle (alleen de item-key nodig; de bundle haalt metadata, notities, annotaties en volledige tekst lokaal op):
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py --item-key ITEMKEY
   # → {"status": "ok", "path": "vault/raw/{citekey}__{itemKey}.md"}
   ```
   Geen bron-inhoud bereikt de Anthropic API — Claude Code ontvangt alleen het JSON-statusobject.
5. Laat de backend de bundle ingesten en (gebatcht) compileren:
   ```bash
   python3 .claude/wiki_backend.py ingest vault --file vault/raw/{citekey}__{itemKey}.md
   python3 .claude/wiki_backend.py compile vault   # drafts → draftsmap van de backend (uitvoer naar log)
   ```
6. **Human review-gate:** de gebruiker beoordeelt de drafts van de geconfigureerde backend in de eigen terminal (voor olw: `olw review --vault vault` — approve → `wiki/`; reject → draft weg + feedback voor de leerloop).
   Claude Code leest geen draftinhoud — het coördineert alleen.
7. Verwijder het item uit de Zotero `_inbox` collectie:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
   ```
8. Vraag: "Nog een paper, of wil je nu iets anders?"

> **Model:** de wiki-generatie draait op `mistral-small:22b` (fast=heavy) via olw en de vault-lokale `wiki.toml` (`heavy_ctx=16384`). olw compileert bestaande kennis uit de bundle — voor zeer lange bronnen kapt olw de conceptdraft-output zonodig af (soft-cap in `wiki.toml`).

### Type 2: Semantisch zoeken op thema

1. Vraag naar het thema en het doel (oriëntatie of gericht zoeken?)
2. Vraag of er aanverwante begrippen zijn om mee te zoeken
3. Voer `zotero_semantic_search` uit met de opgegeven termen; voor bestaande vault-inhoud: `hyalo find "[kernbegrip]"` over `vault/raw/*.md` en `vault/wiki/`
4. Toon resultaten met similariteitsscores — vraag welke interessant zijn
5. Bied aan om de interessante papers direct te verwerken (zie type 1: raw → backend → wiki)
6. Als resultaten mager zijn: stel alternatieve zoektermen voor

### Type 3: YouTube-transcript ophalen en verwerken

> **Fase 1** (dump) is al gedaan: de URL staat in Zotero `_inbox`, opgeslagen via de iOS share sheet vanuit de YouTube-app. Bij een ✅ in de feedreader is het transcript vaak al eager opgehaald.
> **Fase 2** (filter): vraag of de gebruiker de video al beoordeeld heeft, of genereer een beoordeling op basis van metadata.
> **Fase 3** (verwerken): transcript als bijlage in het Zotero-item zetten, daarna via `raw` → backend verwerken.
> **Let op:** `transcript [URL]` slaat de Zotero `_inbox` stap over — de video gaat direct naar verwerking. De gebruiker heeft de video al gefilterd door hem aan te reiken.

1. Haal de URL op uit het `_inbox` item in Zotero, of vraag de gebruiker hem te plakken
2. **Als beoordeling gewenst:** haal metadata op (titel, kanaal, duur, beschrijving) en geef een relevantie-advies; wacht op Go van de gebruiker
3. **Bij Go:** zorg dat het transcript als `.txt`-bijlage in het Zotero-item staat via `attach-transcript.py` (gebruikt de feedreader-cache of `YouTubeTranscriptApi`; genereert lokaal een abstract):
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
     --item-key ITEMKEY --url "https://www.youtube.com/watch?v=..."
   ```
4. Verwerk daarna als een gewone bron — het transcript komt mee in de bundle:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py --item-key ITEMKEY
   python3 .claude/wiki_backend.py ingest vault --file vault/raw/{...}.md
   python3 .claude/wiki_backend.py compile vault   # daarna de reviewstap van de backend
   ```
   De backend genereert de wiki-pagina; timecodes/citaten worden niet als geverifieerde bron opgenomen. **Toon nooit de ruwe transcripttekst.**
5. Verwijder het item uit de Zotero `_inbox`:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
   ```

> **Fallback (losse stap):** ontbreekt de bijlage-route, dan kan het transcript via `fetch-fulltext.py ITEMKEY .cache/{video_id}.txt` naar `.cache/` en desgewenst lokaal verwerkt worden met `ollama-generate.py` (`--backend ollama|mlx`; voor maximale kwaliteit vraag je Claude Code er expliciet om — er is géén `--hd`-vlag op dit script) — nooit `cat`/`print` op de volledige inhoud.

### Type 4: Podcast ophalen en verwerken

> **Fase 1** (dump) is al gedaan: de URL staat in Zotero `_inbox`, opgeslagen via de iOS share sheet vanuit Overcast.
> **Fase 2** (filter): de gebruiker heeft de eerste 5–10 minuten beluisterd, of vraagt Claude Code om shownotities op te halen als hulp bij de beslissing.
> **Fase 3** (verwerken): audio downloaden, transcriberen via whisper.cpp (lokaal, Metal GPU), bijlage in Zotero, daarna via `raw` → backend.
> **Let op:** `podcast [URL]` slaat de Zotero `_inbox` stap over — de podcast gaat direct naar verwerking.

1. Vraag naar de URL — of: "Wil je dat ik de shownotities ophaal zodat je kunt beslissen?" (via de feedreader-cache; anders `enrich-inbox.py`)
2. **Als shownotities gewenst:** geef een samenvatting van 3 zinnen op basis van de show notes; wacht op Go. **Toon nooit de volledige tekst.**
3. **Bij Go:** transcribeer en hang het transcript als bijlage aan het Zotero-item via `attach-transcript.py` (downloadt audio, detecteert de taal uit de show notes, transcribeert via `whisper-cli`, genereert een abstract, hangt de `.txt` aan het item):
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/attach-transcript.py \
     --item-key ITEMKEY --url "https://podcast-episode-pagina-url"
   ```
   Optioneel: `--language nl|en`, `--whisper-model base`, `--force` om te hertranscriberen.
4. Verwerk daarna als een gewone bron (transcript komt mee in de bundle):
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/build-zotero-bundle.py --item-key ITEMKEY
   python3 .claude/wiki_backend.py ingest vault --file vault/raw/{...}.md
   python3 .claude/wiki_backend.py compile vault   # daarna de reviewstap van de backend
   ```
5. Verwijder het item uit de Zotero `_inbox`:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/zotero-remove-from-inbox.py ITEMKEY
   ```
   Het tijdelijke audiobestand (`.cache/_audio_{ITEMKEY}.mp3`) wordt door `attach-transcript.py` automatisch opgeruimd.

### Type 5: RSS-items verwerken

> **Fase 1** (breed vangen): de feedreader (`feedreader-score.py`) heeft de feeds gescoord en gesorteerd. NetNewsWire toont de gefilterde Atom-feeds via FreshRSS. De gebruiker heeft interessante items naar Zotero `_inbox` gestuurd via de actieknoppen in NNW of de iOS share sheet.
> **Fase 2** (filter): de gebruiker heeft kopteksten gescand; alleen interessante items komen hier.
> **Fase 3** (verwerken): via Zotero → `raw` → backend, of als los denkwerk via `promote-to-raw.py`.

1. Vraag: wil je het item toevoegen aan Zotero (voor BibTeX, annotaties en opname in de semantische database), of gaat het om eigen denkwerk?
2. **Via Zotero:** het item is al opgeslagen via de Zotero Connector of iOS-app; verwerk het naar de wiki zoals type 1 (build-zotero-bundle → backend-ingest → compile → review)
3. **Eigen denkwerk / losse notitie:** schrijf de notitie in `authoring/notes/` (of geef `inbox [URL]` om de inhoud lokaal op te halen als Markdown in `.cache/`), en promoveer die daarna naar de bronlaag:
   ```bash
   ~/.local/share/uv/tools/zotero-mcp-server/bin/python3 .claude/promote-to-raw.py --note <pad>
   # → schone snapshot naar vault/raw/notes/<slug>.md (source_type: personal) + backend-ingest
   ```
4. Zotero-tags komen mee in de bundle-frontmatter; de backend (nu olw) beheert de wiki-pagina en cross-links.

### Type 6: Synthese maken (via de backend)

Syntheses zijn **het domein van de backend**: de backend (nu olw) legt thematische syntheses (`wiki/syntheses/`) en cross-links aan tijdens de compile-stap, gestuurd door zijn eigen config (voor olw `wiki.toml`). Claude Code schrijft geen synthese met de hand.

1. Vraag naar het thema en het doel van de synthese
2. Breng in kaart wat er al is: `hyalo find "[thema]"` over `vault/wiki/` (bestaande concepten + syntheses) en `vault/raw/*.md` (welke bronnen zijn al ge-ingest?)
3. Toon een overzicht van gevonden materiaal — klopt dit? Ontbreken er bronnen die eerst ge-ingest moeten worden (zie type 1)?
4. Draai de backend om (opnieuw) te compileren zodat de synthese en cross-links worden bijgewerkt (uitvoer naar een log):
   ```bash
   python3 .claude/wiki_backend.py compile vault   # de backend legt cross-links + syntheses aan
   ```
   Een gerichte hercompilatie van losse concepten is backend-eigen en loopt niet via de dispatcher; ondersteunt de backend het, dan draait de gebruiker dat commando zelf (voor olw: `olw compile --vault vault --concept "[naam]"`, herhaalbaar).
5. **Human review-gate:** de gebruiker keurt de synthese-draft goed:
   ```bash
   olw review --vault vault
   ```
6. Voor eigen synthetiserend denkwerk dat geen bron ís: schrijf het in `authoring/notes/` en promoveer via `promote-to-raw.py` → `raw/notes/` → backend.

### Type 7: Wiki doorbladeren en verbanden bewaken

Navigatie, zoeken en link-management lopen via **hyalo** (geen LLM). De cross-links en structuur zelf zijn het domein van de backend (nu olw).

1. Geef een overzicht van `wiki/` (concepten, `sources/`, `syntheses/`) en `raw/` via hyalo
2. Vraag: wil je binnen een specifiek thema kijken, of breed over de hele wiki?
3. Signaleer wiki-gezondheidsproblemen met de backstops van de backend (nu `olw lint` / `olw maintain`):
   ```bash
   olw lint --vault vault           # orphans, broken links, stubs
   olw maintain --vault vault       # onderhoud op basis van de lint-bevindingen
   ```
4. Stel voor om ontbrekende bronnen te ingesten of `python3 .claude/wiki_backend.py compile vault` te draaien als concepten stub blijven; de daadwerkelijke `[[links]]` legt de backend aan tijdens compile — niet met de hand.

### Type 8: Inbox opruimen

1. Toon wat er in `.cache/` staat (temp-bestanden: `_summary_*.md`, transcripten, snapshots, `_audio_*.mp3`)
2. Per item: is de bron al verwerkt naar `raw/` + olw? Zo ja → opruimen; zo nee → alsnog verwerken (type 1/3/4) of verwijderen
3. Verwijder verwerkte transcripten en samenvattingen
4. Bevestig na afloop: "Inbox is leeg. Alles verwerkt."

---

## Toon en stijl

- Communiceer in het Nederlands, tenzij de gebruiker in een andere taal schrijft
- Wees direct en bondig — geen overbodige uitleg als de gebruiker al weet wat er gebeurt
- Stel nooit meer dan twee vragen tegelijk
- Als iets onduidelijk is, gok dan niet: vraag het
- Als een zoekopdracht weinig oplevert, zeg dat eerlijk en stel alternatieven voor
- Denk proactief mee: signaleer als iets ontbreekt, verouderd is, of beter kan
- **Privacy-grens:** toon nooit bron- of draftinhoud als tool-output; backend-uitvoer gaat naar een log, je leest alleen exit-code/tellingen/paden

---

## Snelkoppelingen die Claude Code herkent

| Zin van gebruiker | Actie |
|---|---|
| "feedreader" of "voeg feed toe" | Start type F: beheer feedreader-feeds of instellingen |
| "score feeds" of "run feedreader" | Draai `feedreader-score.py` handmatig |
| "drempeladvies" | Draai `feedreader-learn.py` en toon drempeladvies |
| "beoordeel inbox" of "filter inbox" | Start type 0: haal `_inbox` op uit Zotero, geef per item een Go/No-go beoordeling (samenvatting via `summarize_item.py`, volledig lokaal) |
| "beoordeel inbox --hd" | Start type 0 met Claude Sonnet 4.6 voor de samenvattingen (na bevestiging) |
| "verwerk recente papers" | Start type 1 (raw → backend → wiki, lokaal via `mistral-small:22b`) |
| "zoek op [thema]" | Start type 2 met opgegeven thema |
| "transcript [URL]" | Start type 3 met de opgegeven URL; transcript-bijlage → raw → backend; slaat Zotero `_inbox` over |
| "transcript [URL] --hd" | Start type 3; de losse `ollama-generate.py`-fallback via Claude Sonnet 4.6 (na bevestiging) |
| "podcast [URL]" | Start type 4: transcribeer via whisper.cpp → bijlage → raw → backend; slaat Zotero `_inbox` over |
| "inbox [URL]" | Haal artikel op en sla op als Markdown in `.cache/`, zonder Zotero |
| "rss [URL of item]" | Start type 5 voor het opgegeven item |
| "synthese over [thema]" | Start type 6 (via de compile/review-stap van de backend) |
| "wat staat er in de wiki" | Start type 7, geef overzicht via hyalo |
| "compile" | Draai `python3 .claude/wiki_backend.py compile vault` (uitvoer naar log); daarna de reviewstap van de geconfigureerde backend |
| "review drafts" | Herinner de gebruiker aan de `olw review --vault vault`-gate in de eigen terminal |
| "ruim inbox op" | Start type 8 |
| "update database" | Voer `zotero-mcp update-db --fulltext` uit |
| "wat heb ik gisteren gedaan" | Zoek in `notes/` naar de meest recente dagnotitie |

---

*Skill versie 2.0 — juli 2026 — raw→olw-reconciliatie: `process_item.py`→`literature/` vervangen door `build-zotero-bundle.py`→`raw/`→olw ingest/compile/`olw review`→`wiki/`; model `mistral-small:22b` (olw), qwen alleen fallback; transcripten via `attach-transcript.py`→bundle; syntheses = olw's domein; flashcards/spaced-repetition verwijderd. (Historische notitie — sinds de wiki-backend-contract-wijziging is de backend geconfigureerd via `wiki-backend.toml`/`.claude/wiki_backend.py`; lees "olw" hierboven als de toenmalige/huidige keuze, niet als vaste component.)*
