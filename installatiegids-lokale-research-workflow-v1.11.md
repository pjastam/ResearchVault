# Installatiegids: Lokale Research Workflow
## Claude Code + Zotero MCP + Obsidian + Ollama op macOS (M4)

**Doel:** Een volledig lokale, privacy-vriendelijke research workflow opzetten op een Mac mini M4 (2024), waarbij Zotero, Claude Code, Obsidian en Ollama samenwerken zonder afhankelijkheid van externe clouddiensten voor je data. De workflow volgt een **3-fasen model**: breed vangen → filteren → verwerken.

**Geschatte installatietijd:** 60–120 minuten  
**Vereisten:** macOS Sequoia of hoger, internetverbinding voor downloads, een Anthropic-account (voor Claude Code)

---

## Het 3-fasen model

De workflow is opgebouwd rond drie expliciete fasen — elke bron doorloopt ze alle drie:

| Fase                        | Doel                                        | Werkwijze                                                                                                                                                                                  |
| --------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1 — Breed vangen**        | Lage drempel, geen filtering                | Per bron een eigen dump-laag: Browser (Zotero Connector/iOS), NetNewsWire (RSS), Overcast (podcasts), YouTube (video's), Overig (iOS share sheet) — alles stroomt samen in Zotero `_inbox` |
| **2 — Filteren**            | Jij beslist wat de vault in mag             | Claude Code genereert een samenvatting; jij geeft Go of No-go                                                                                                                              |
| **3 — Verwerken & opslaan** | Volledige verwerking van goedgekeurde items | Claude Code → Obsidian vault                                                                                                                                                               |

Het onderscheid tussen fase 1 en fase 3 voorkomt dat je vault vervuilt met materiaal dat je op het moment van vangen interessant leek maar bij nader inzien niet relevant is.

---

## Overzicht van de stappen

1. Homebrew installeren (pakketbeheer)
2. Zotero 7 installeren en configureren **(inclusief `_inbox` collectie)**
3. Python-omgeving opzetten
4. Zotero MCP installeren en configureren
5. Claude Code installeren
6. Ollama installeren (lokaal taalmodel)
7. Obsidian installeren en vault aanmaken
8. Alles koppelen: Claude Code configureren met MCP
9. Eerste test uitvoeren
10. Optionele uitbreidingen (yt-dlp, semantisch zoeken, automatische updates)
11. Podcast-integratie (whisper.cpp)
12. RSS-integratie (Zotero feeds + NetNewsWire)
13. Spaced repetition (Obsidian plugin)
14. Filterlaag inrichten per bron

---

## Stap 1: Homebrew installeren

Homebrew is de standaard pakketbeheerder voor macOS en vereenvoudigt de installatie van alle verdere tools.

Open Terminal (te vinden via Spotlight: `Cmd + Spatie` → typ "Terminal") en voer het volgende commando uit:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Volg de instructies op het scherm. Na installatie voeg je Homebrew toe aan je shell-pad (het installatiescript toont dit commando aan het einde — kopieer en voer het uit).

Controleer of de installatie gelukt is:

```bash
brew --version
```

---

## Stap 2: Zotero 7 installeren en configureren

### 2a. Zotero downloaden

Download Zotero 7 via [zotero.org](https://www.zotero.org/download/). Installeer de applicatie door de `.dmg` te openen en Zotero naar je programmamap te slepen.

### 2b. Lokale API inschakelen

Dit is de cruciale stap die Zotero MCP mogelijk maakt:

1. Open Zotero
2. Ga naar **Zotero → Instellingen → Geavanceerd** (of `Cmd + ,`)
3. Scrol naar beneden naar het gedeelte **Overige**
4. Zet het vinkje aan bij **"Andere applicaties op deze computer toestaan om met Zotero te communiceren"**
5. Noteer het poortnummer dat verschijnt (standaard: `23119`)

> **Privacy-noot:** Deze API is alleen toegankelijk via `localhost` — er is geen externe toegang mogelijk.

### 2c. Controleer of de lokale API werkt

Open een nieuw tabblad in je browser en ga naar:

```
http://localhost:23119/
```

Je zou een JSON-respons moeten zien met versie-informatie van Zotero. Als dat lukt, werkt de lokale API correct.

### 2d. `_inbox` collectie aanmaken (centrale verzamelbucket)

In het 3-fasen model is Zotero's `_inbox` collectie niet een bron op zichzelf, maar de centrale verzamelbucket waar alle bronnen naartoe stromen: documenten via de Zotero Connector of iOS-app, RSS-items via NetNewsWire, podcasts en video's via de Zotero iOS share sheet, en e-mail of notities via de iOS deelknop. Je beoordeelt de inhoud pas in fase 2 (zie stap 14).

1. Klik in Zotero rechts op **Mijn bibliotheek** → **Nieuwe collectie**
2. Noem de collectie `_inbox` (de underscore zorgt dat hij bovenaan de lijst staat)
3. Stel dit als standaard-bestemming in de Zotero Connector: open de browser-extensie → **Instellingen** → zet de standaardcollectie op `_inbox`
4. Stel dezelfde standaard in op iOS: open de Zotero-app → **Instellingen** → zet de standaard-verzamellocatie op `_inbox`

Voortaan gaat alles wat je opslaat via de Connector of de iOS share sheet automatisch naar `_inbox`. Je kunt ook direct een notitie aanmaken binnen de Zotero-app zelf — die belandt eveneens in de `_inbox` als je die als standaard hebt ingesteld.

### 2e. Better BibTeX plugin installeren (aanbevolen)

Better BibTeX verbetert de annotatie-extractie aanzienlijk:

1. Download de nieuwste `.xpi` van [retorque.re/zotero-better-bibtex/installation](https://retorque.re/zotero-better-bibtex/installation/)
2. In Zotero: **Extra → Plugins → Tandwiel-icoon → Installeer vanuit bestand**
3. Selecteer het gedownloade `.xpi` bestand
4. Herstart Zotero

---

## Stap 3: Python-omgeving opzetten

Zotero MCP vereist Python 3.10 of hoger. Op Apple Silicon werkt `uv` als snelle, moderne pakketbeheerder het beste.

### 3a. uv installeren (aanbevolen)

```bash
brew install uv
```

Controleer de installatie:

```bash
uv --version
```

### 3b. Controleer Python-versie

```bash
python3 --version
```

Als de versie lager is dan 3.10, installeer je een nieuwere versie:

```bash
brew install python@3.12
```

---

## Stap 4: Zotero MCP installeren en configureren

### 4a. Installeer het pakket

```bash
uv tool install zotero-mcp-server
```

Controleer of de installatie gelukt is:

```bash
zotero-mcp version
```

### 4b. Voer de setup-wizard uit

```bash
zotero-mcp setup
```

De wizard stelt je een aantal vragen:

- **Toegangsmethode:** kies `local` (geen API-sleutel nodig, volledig offline)
- **MCP-client:** kies `Claude Desktop` als je die later installeert, of sla over
- **Semantisch zoeken:** je kunt dit nu overslaan en later configureren (zie stap 10)

### 4c. Semantische zoekopdracht initialiseren

Bouw de lokale zoekdatabase op (gebruikt het gratis, lokaal draaiende model `all-MiniLM-L6-v2`):

```bash
# Snelle versie (alleen metadata):
zotero-mcp update-db

# Uitgebreide versie (inclusief volledige tekst — aanbevolen):
zotero-mcp update-db --fulltext
```

> **Let op:** De `--fulltext` optie duurt langer maar geeft veel betere zoekresultaten. Op een M4 Mac mini met een gemiddelde bibliotheek duurt dit 5–20 minuten.

Controleer de status van de database:

```bash
zotero-mcp db-status
```

---

## Stap 5: Claude Code installeren

### 5a. Node.js installeren

```bash
brew install node
```

### 5b. Claude Code installeren

```bash
npm install -g @anthropic-ai/claude-code
```

### 5c. Authenticeren

```bash
claude
```

Bij de eerste keer opstarten wordt je gevraagd in te loggen met je Anthropic-account. Volg de instructies in de terminal.

---

## Stap 6: Ollama installeren (lokaal taalmodel)

### Lokaal vs. cloud — wat gebeurt waar?

Het is belangrijk te begrijpen wat er in deze workflow lokaal draait en wat via de cloud verloopt:

| Stap | Waar | Toelichting |
|------|------|-------------|
| Zotero MCP (bibliotheek opvragen) | ✅ Lokaal | Verbinding via `localhost` |
| yt-dlp (transcripten ophalen) | ✅ Lokaal | Scraping op je Mac |
| whisper.cpp (audio transcriberen) | ✅ Lokaal | M4 Metal GPU |
| Semantisch zoeken (Zotero MCP) | ✅ Lokaal | Lokale vectordatabase |
| **Redeneren, samenvatten, synthese schrijven** | ⚠️ **Cloud** | Prompt + context gaan naar Anthropic API |

Die laatste stap is de kern van wat Claude Code doet: elke keer dat je een samenvatting, literatuurnotitie of synthese laat maken, stuurt Claude Code de volledige tekst als prompt naar de Anthropic API. Dat is effectief maar verbruikt tokens en verlaat je machine.

**Ollama lost dit op:** als je Ollama configureert als motor voor synthesetaken, draait het redeneerwerk volledig lokaal op je M4. Geen tokens, geen dataoverdracht. De M4 met 24 GB is daar krachtig genoeg voor.

**Het eerlijke compromis:** lokale modellen zijn minder capabel dan Claude Sonnet voor complexe of genuanceerde taken. Voor eenvoudige samenvattingen en flashcards is het verschil klein; voor het schrijven van rijke literatuurnotities of het leggen van subtiele verbanden tussen bronnen is Claude Sonnet merkbaar beter. Een hybride aanpak — Ollama voor routinematige taken, Claude Code voor het werk waarbij kwaliteit telt — is voor de meeste gebruikers het meest praktisch.

---

### 6a. Installeren

```bash
brew install ollama
```

### 6b. Modellen downloaden

Voor een M4 Mac mini met 24 GB geheugen is **Qwen3.5:9b** het aanbevolen standaardmodel voor alle lokale verwerkingstaken in de workflow:

```bash
ollama pull qwen3.5:9b   # ~6.6 GB — standaardmodel voor alle taken
```

Qwen3.5:9b heeft een contextvenster van 256K tokens, recente training met expliciete aandacht voor meertaligheid (201 talen, inclusief Nederlands), en een hybride architectuur die ook bij lange invoer snel blijft. Het vervangt zowel llama3.1:8b als mistral voor alle workflow-taken.

```bash
# Optionele alternatieven (niet nodig als je qwen3.5:9b gebruikt):
ollama pull llama3.1:8b   # ~4.7 GB — bewezen, maar 128K context en minder meertalig
ollama pull phi3           # ~2.3 GB — zeer compact, voor systemen met minder geheugen
```

Controleer welke modellen beschikbaar zijn na het downloaden:

```bash
ollama list
```

### 6c. Ollama starten

```bash
ollama serve
```

Laat dit draaien in een apart Terminal-venster, of configureer het als achtergrondservice zodat het altijd beschikbaar is:

```bash
# Automatisch starten bij systeemopstart (aanbevolen):
brew services start ollama
```

Controleer of Ollama actief is en welke modellen beschikbaar zijn:

```bash
ollama list
```

### 6d. Ollama inrichten als motor voor synthesetaken

Claude Code kan via zijn bash-tool Ollama aanroepen voor taken die je lokaal wilt afhandelen. De eenvoudigste manier is om Claude Code expliciet te instrueren wanneer je een lokale verwerking wilt.

**Optie 1: Per taak expliciet aangeven (eenvoudigst)**

Typ in Claude Code bij elke taak waarvoor je Ollama wilt gebruiken:

```
Gebruik Ollama (qwen3.5:9b) om een samenvatting te maken van dit transcript.
Roep het model aan via: ollama run qwen3.5:9b
```

Claude Code voert dan het commando lokaal uit via de bash-tool en verwerkt de output zonder een Anthropic API-aanroep te doen voor die stap.

**Optie 2: Standaardregel in CLAUDE.md**

Voeg een sectie toe aan je `CLAUDE.md` om Claude Code te instrueren standaard Ollama te gebruiken voor alle verwerkingstaken:

```markdown
## Lokale verwerking via Ollama

Standaard verloopt alle verwerking lokaal via Qwen3.5:9b. Gebruik dit voor:
- Literatuurnotities op basis van papers of transcripten
- Thematische syntheses
- Flashcard-generatie

Roep Ollama aan via de bash-tool:
`ollama run qwen3.5:9b < inbox/[bestandsnaam].txt`

**Maximale kwaliteitsmodus:** als de gebruiker `--hd` toevoegt of expliciet vraagt om "maximale kwaliteit" of "gebruik Sonnet", schakel dan over naar Claude Sonnet 4.6 via de Anthropic API. Meld dit altijd eerst en wacht op bevestiging voordat je de API-aanroep doet. Val nooit automatisch terug op Sonnet als Qwen niet bereikbaar is — meld dat Ollama niet actief is en vraag wat de gebruiker wil.
```

**Optie 3: Testen of Ollama bereikbaar is**

Verifieer vanuit Claude Code of Ollama actief is en een testprompt verwerkt:

```bash
ollama run qwen3.5:9b "Geef een samenvatting van drie zinnen over substitutiezorg."
```

Als dit een antwoord geeft, is Ollama klaar voor gebruik vanuit Claude Code.

---

## Stap 7: Obsidian installeren en vault aanmaken

### 7a. Obsidian downloaden

Download Obsidian via [obsidian.md](https://obsidian.md). Installeer de applicatie op de gebruikelijke manier.

### 7b. Een vault aanmaken

1. Open Obsidian
2. Kies **"Nieuwe vault aanmaken"**
3. Geef de vault een naam, bijv. `ResearchVault`
4. Kies een locatie die je goed onthoudt, bijv. `~/Documents/ResearchVault`
5. Klik op **"Aanmaken"**

### 7c. Mapstructuur aanmaken

Maak de volgende mappen aan in je vault (klik rechts in het linker paneel → "Nieuwe map"):

```
ResearchVault/
├── literature/          ← samenvattingen van Zotero-papers, YouTube en podcasts
│   └── annotations/     ← geëxtraheerde PDF-annotaties
├── syntheses/           ← thematische dwarsverbanden
├── projects/            ← per project of samenwerking
├── daily/               ← dagelijkse notities
├── flashcards/          ← spaced repetition kaarten (optioneel, los van literature/)
└── inbox/               ← ruwe input, nog te verwerken
```

### 7d. CLAUDE.md aanmaken

Maak een bestand `CLAUDE.md` aan in de **root van je vault** (niet in een submap). Dit is het geheugen van Claude Code. Plak hierin de volgende starttekst en pas aan naar eigen voorkeur:

```markdown
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
Elke literatuurnotitie bevat:
- Bibliografische gegevens (auteur, jaar, tijdschrift)
- Kernvraag en hoofdargument
- Kernbevindingen (3–5 punten)
- Methodologische notities
- Citaten die relevant zijn voor mijn onderzoek
- Links naar gerelateerde notes in de vault

## Taal
- Antwoord in het Nederlands tenzij anders gevraagd
- Schrijf literatuurnotities in het Nederlands, citaten in de originele taal

## Zotero-workflow
- Gebruik Zotero MCP om papers op te halen via hun titel of sleutelwoorden
- Sla literatuurnotities op als `literature/[auteur-jaar-kernwoord].md`
- Voeg altijd een #tag toe voor het thema van de paper

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

## RSS-feeds
- Alle RSS-feeds (academisch én niet-academisch) worden gevolgd via NetNewsWire
- Academische artikelen die interessant zijn: voeg ze toe aan Zotero via de browser-extensie of iOS-app → komen in `_inbox` terecht
- Niet-academische artikelen: voeg toe via Zotero Connector, of geef de URL door met `inbox [URL]` voor directe opslag als Markdown in `inbox/`
- Bestandsnaam voor RSS-items zonder Zotero-record: `[bron-jaar-kernwoord].md` met #tag `#web` of `#beleid`

## Spaced repetition (Obsidian plugin)
- Flashcards worden aangemaakt na elke literatuurnotitie of synthese
- Formaat: vraag en antwoord gescheiden door `?` op een nieuwe regel, omsloten door `#flashcard`-tag
- Maak maximaal 5 kaarten per bron — kies de meest relevante concepten
- Dagelijkse review via Obsidian Spaced Repetition plugin (zijbalk → Kaarten beoordelen)
```

---

## Stap 8: Claude Code koppelen aan Zotero MCP

### 8a. Configuratiebestand aanpassen

Claude Code leest de MCP-configuratie uit `~/Library/Application Support/Claude/claude_desktop_config.json`. Dit is dezelfde locatie als Claude Desktop gebruikt. Maak of bewerk dit bestand:

```bash
mkdir -p ~/Library/Application\ Support/Claude
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Voeg het volgende in (of voeg de `zotero`-sectie toe aan een bestaand bestand):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "zotero-mcp",
      "env": {
        "ZOTERO_LOCAL": "true"
      }
    }
  }
}
```

Sla op met `Ctrl + O`, `Enter`, dan `Ctrl + X`.

### 8b. Controleer de MCP-configuratie

```bash
zotero-mcp setup-info
```

Dit toont het installatiepad en de configuratie zoals Zotero MCP die ziet.

---

## Stap 9: Eerste test uitvoeren

### 9a. Start Zotero

Zorg dat Zotero 7 open en actief is (de lokale API is alleen beschikbaar als Zotero draait).

### 9b. Open Claude Code in je vault

```bash
cd ~/Documents/ResearchVault
claude
```

### 9c. Testprompts uitvoeren

Probeer de volgende prompts in Claude Code om te controleren of alles werkt:

**Test 1 — Zotero-verbinding:**
```
Zoek in mijn Zotero-bibliotheek naar recente toevoegingen en geef een overzicht.
```

**Test 2 — Paper ophalen:**
```
Zoek een paper over [een thema dat je in Zotero hebt] en schrijf een literatuurnotitie 
naar literature/ in Obsidian-formaat.
```

**Test 3 — Semantisch zoeken:**
```
Gebruik semantisch zoeken om papers te vinden die conceptueel gerelateerd zijn aan [thema].
```

**Test 4 — Vault-bewustzijn:**
```
Bekijk de structuur van deze vault en geef een samenvatting van wat er al in staat.
```

Als alle vier de tests werken, is de basisinstallatie geslaagd.

---

## Stap 10: Optionele uitbreidingen

### 10a. yt-dlp installeren (YouTube-transcripten)

Met yt-dlp kun je transcripten van YouTube-video's ophalen en als bron in je vault opslaan. Dit is nuttig voor lezingen, conferentie-opnames, interviews en andere wetenschappelijke video-inhoud.

#### Installeren

```bash
brew install yt-dlp
```

Controleer de installatie:

```bash
yt-dlp --version
```

#### Een transcript ophalen

De basisopdracht om een automatisch gegenereerd ondertitelbestand te downloaden:

```bash
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  "https://www.youtube.com/watch?v=VIDEOID" -o "transcript"
```

Dit maakt een `.vtt`-bestand aan in je huidige map. De VTT-indeling bevat tijdcodes en is direct leesbaar als tekst.

Voor video's waarbij je handmatige ondertitels wilt ophalen als die beschikbaar zijn (beter van kwaliteit dan automatisch gegenereerde):

```bash
# Handmatige ondertitels ophalen (indien beschikbaar), anders automatisch:
yt-dlp --write-sub --write-auto-sub --skip-download \
  --sub-lang nl,en --sub-format vtt \
  "https://www.youtube.com/watch?v=VIDEOID" -o "~/Documents/ResearchVault/inbox/%(title)s"
```

De vlaggen `--write-sub --write-auto-sub` werken voor alle talen op dezelfde manier: yt-dlp pakt handmatige ondertitels als die beschikbaar zijn, en valt anders terug op automatisch gegenereerde. `--sub-lang nl,en` vraagt beide talen op — handig voor tweetalige content. De optie `-o "...%(title)s"` gebruikt automatisch de videotitel als bestandsnaam, zodat je weet wat je hebt opgeslagen.

#### Integreren in de vault-workflow

Sla transcripten altijd op in `inbox/` en vraag Claude Code ze te verwerken:

```bash
# Stap 1: transcript ophalen naar inbox
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  "https://www.youtube.com/watch?v=VIDEOID" \
  -o "~/Documents/ResearchVault/inbox/%(title)s"

# Stap 2: open Claude Code in je vault
cd ~/Documents/ResearchVault
claude
```

Geef dan aan Claude Code de instructie:

```
Verwerk het transcript in inbox/ naar een gestructureerde note in literature/ 
met samenvatting, kernpunten en tijdgestempelde citaten.
```

#### Meerdere video's tegelijk (zoekresultaten)

Je kunt ook zoekresultaten van YouTube batchgewijs ophalen. Je hoeft het commando hiervoor niet zelf te typen: je kunt Claude Code in gewone taal instrueren, bijvoorbeeld:

```
Haal de eerste tien YouTube-video's op over "implementatie zorgakkoord Nederland" 
en sla de transcripten op in inbox/
```

Claude Code schrijft en voert het yt-dlp-commando zelf uit. De onderliggende opdracht ziet er als volgt uit:

```bash
# De eerste 10 video's over een zoekterm ophalen:
yt-dlp --write-auto-sub --skip-download --sub-format vtt \
  "ytsearch10:implementatie zorgakkoord Nederland" \
  -o "~/Documents/ResearchVault/inbox/%(title)s"
```

> **Privacy-noot:** yt-dlp maakt alleen verbinding met YouTube om de publiek beschikbare ondertitelbestanden te downloaden. Er worden geen persoonlijke gegevens verstuurd en er is geen account vereist.

### 10b. Betere semantische embeddings (optioneel)

Het standaard lokale model (`all-MiniLM-L6-v2`) is gratis en snel. Als je betere zoekresultaten wilt en bereid bent een OpenAI API-sleutel te gebruiken alleen voor embeddings (niet voor tekstgeneratie):

```bash
zotero-mcp setup --semantic-config-only
```

Kies dan `openai` als embedding-model en voer je API-sleutel in. Herinitialiseer daarna de database:

```bash
zotero-mcp update-db --fulltext --force-rebuild
```

### 10c. Automatische database-updates

Elke keer dat je nieuwe papers toevoegt aan Zotero, moet de semantische zoekdatabase worden bijgewerkt om die papers te kunnen vinden. Je kunt dit handmatig doen, maar automatisering is comfortabeler.

#### Optie 1: Via de Zotero MCP setup-wizard (eenvoudigst)

```bash
zotero-mcp setup --semantic-config-only
```

Kies bij de updatefrequentie voor **"Daily"** of **"Auto on startup"**. Met "Auto on startup" wordt de database bijgewerkt elke keer dat Claude Code Zotero MCP aanroept — dat is de meest hands-off aanpak.

> **Over "unknown" als modelnaam:** Na het uitvoeren van `zotero-mcp setup-info` kan de embedding-modelnaam als `unknown` worden weergegeven. Dit is normaal gedrag: het standaard lokale model (`all-MiniLM-L6-v2`) wordt gebruikt, maar de naam wordt niet teruggemeld door de setup-info. Je installatie werkt gewoon. Verificatie doe je niet via de terminal maar via Claude Code: vraag na het uitvoeren van `zotero-mcp update-db` in Claude Code om semantisch te zoeken op een term die in je bibliotheek voorkomt. Als dat resultaten geeft, werkt de database correct.

#### Optie 2: Handige alias in je shell-profiel

Voeg een alias toe zodat je met één commando de database kunt bijwerken:

```bash
# Open je shell-configuratiebestand:
nano ~/.zshrc
```

Voeg onderaan toe:

```bash
# Zotero MCP hulpcommando's
alias update-zotero="zotero-mcp update-db --fulltext"
alias zotero-status="zotero-mcp db-status"
```

Activeer de wijzigingen:

```bash
source ~/.zshrc
```

Daarna kun je altijd simpelweg typen:

```bash
update-zotero
```

#### Optie 3: Geautomatiseerd via macOS launchd (achtergrondtaak)

Voor volledig automatische dagelijkse updates kun je een macOS launchd-taak instellen. Maak een nieuw bestand aan:

```bash
nano ~/Library/LaunchAgents/com.zotero-mcp.update.plist
```

Plak hierin:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.zotero-mcp.update</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-c</string>
    <string>zotero-mcp update-db --fulltext >> ~/Documents/ResearchVault/zotero-mcp-update.log 2>&1</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

Dit voert dagelijks om 08:00 een database-update uit en slaat het logboek op in je vault. Activeer de taak:

```bash
launchctl load ~/Library/LaunchAgents/com.zotero-mcp.update.plist
```

> **Let op:** Voor de launchd-optie moet Zotero open zijn op het moment dat de update draait. Als je Mac op dat tijdstip in slaapstand staat, wordt de taak overgeslagen tot de volgende dag.

---

## Stap 11: Podcast-integratie (whisper.cpp)

Met whisper.cpp kun je podcasts en andere geluidsopnames volledig lokaal transcriberen op je M4 Mac mini. De M4-chip voert dit via Metal (de GPU) razendsnel uit: een uur audio duurt ongeveer 3–5 minuten.

### 11a. whisper.cpp installeren

```bash
brew install whisper-cpp
```

Controleer de installatie:

```bash
whisper-cpp --version
```

### 11b. Een podcast downloaden en transcriberen

yt-dlp ondersteunt veel podcastplatforms naast YouTube (SoundCloud, Podbean, directe MP3-links via RSS). De volledige pipeline in twee stappen:

```bash
# Stap 1: audio downloaden naar inbox/
yt-dlp -x --audio-format mp3 \
  "https://[podcast-url]" \
  -o "~/Documents/ResearchVault/inbox/%(title)s.%(ext)s"

# Stap 2: transcriberen — whisper detecteert de taal automatisch
whisper-cpp --model small \
  ~/Documents/ResearchVault/inbox/[bestandsnaam].mp3
```

Dit maakt een `.txt`- en een `.vtt`-bestand aan naast de `.mp3`. Het `.txt`-bestand bevat de transcriptie zonder tijdcodes; het `.vtt`-bestand bevat tijdcodes per fragment.

**Taal**

Whisper detecteert de taal automatisch op basis van de eerste seconden audio. Voor de meeste eentalige podcasts (Nederlands of Engels) werkt dit prima en hoef je niets in te stellen. Geef `--language` alleen expliciet mee als je problemen ondervindt, bijvoorbeeld bij meertalige content of als de automatische detectie de verkeerde taal kiest:

```bash
# Alleen nodig bij detectieproblemen:
whisper-cpp --model small --language nl ~/Documents/ResearchVault/inbox/[bestand].mp3
whisper-cpp --model small --language en ~/Documents/ResearchVault/inbox/[bestand].mp3
```

In de dagelijkse workflow laat Claude Code de taal automatisch detecteren op basis van de metadata (podcasttitel, kanaal, beschrijving) en geeft `--language` alleen expliciet mee als die metadata onduidelijk is.

**Modellen en kwaliteit**

| Model | Grootte | Snelheid (1 uur audio) | Kwaliteit |
|---|---|---|---|
| `base` | ~145 MB | ~2 min | Goed voor duidelijke spraak |
| `small` | ~465 MB | ~4 min | Aanbevolen startpunt |
| `medium` | ~1.5 GB | ~8 min | Beter voor accenten, snel gesproken |
| `large` | ~3 GB | ~15 min | Beste kwaliteit |

Modellen worden automatisch gedownload bij het eerste gebruik.

### 11c. Verwerken in de vault

Nadat het transcript beschikbaar is in `inbox/`, open je Claude Code in je vault:

```bash
cd ~/Documents/ResearchVault
claude
```

Geef de instructie:

```
Verwerk het podcasttranscript in inbox/[bestandsnaam].txt naar een gestructureerde 
note in literature/ met samenvatting, kernpunten en tijdgestempelde citaten.
```

Claude Code volgt de conventies uit `CLAUDE.md` (zie stap 7d): titel, spreker, samenvatting, kernpunten met tijdcodes, en links naar gerelateerde vault-notes.

> **Privacy-noot:** whisper.cpp draait volledig lokaal op je M4. Er verlaat geen audio je machine.

### 11d. Snelkoppeling: volledige pipeline in één stap

Je kunt ook Claude Code de volledige pipeline laten uitvoeren met één instructie:

```
podcast https://[url-naar-aflevering]
```

Claude Code downloadt de audio, bepaalt de taal automatisch op basis van de metadata, voert whisper.cpp uit, en verwerkt het transcript naar een literatuurnotitie — zie ook de skill (stap "skill activeren"). De Zotero `_inbox` stap wordt overgeslagen: de podcast gaat direct naar Obsidian. Dit is bedoeld voor afleveringen die je al hebt beoordeeld en goedgekeurd.

---

## Stap 12: RSS-integratie

In het 3-fasen model zijn RSS-readers dump-lagen voor fase 1: je abonneert je op feeds zonder direct te beoordelen of elk item relevant is. Pas in fase 2 besluit je wat de vault in gaat.

### 12a. RSS-feeds via NetNewsWire

NetNewsWire is een gratis, open-source RSS-lezer voor macOS en iOS, met iCloud-sync tussen beide apparaten. Het is de centrale dump-laag voor alle RSS-feeds — zowel academisch als niet-academisch. Dit geldt in het bijzonder als je voornamelijk op iOS werkt: de Zotero iOS-app heeft geen ingebouwde RSS-functionaliteit, waardoor NetNewsWire de meest praktische keuze is voor alle feeds.

**Installeren:**

```bash
brew install --cask netnewswire
```

Of download via [netnewswire.com](https://netnewswire.com).

**Aanbevolen feeds:**
- Tijdschrift-RSS (bijv. BMJ, NEJM, TSG)
- PubMed-zoekopdrachten als RSS-feed
- Beleidssites en overheidsnieuwsbrieven
- Vakblogs en opiniestukken over gezondheidsbeleid (bijv. Zorgvisie, Skipr)
- Substack-publicaties van relevante auteurs (elk heeft een RSS-feed via `[naam].substack.com/feed`)

**Nuttige RSS-URL's:**

```
# PubMed-zoekopdracht als RSS (vervang de zoekterm):
https://pubmed.ncbi.nlm.nih.gov/rss/search/?term=[zoekterm]&format=abstract

# Tijdschrift-RSS (voorbeeld BMJ):
https://www.bmj.com/rss/ahead-of-print.xml

# Google Scholar-meldingen (via e-mail instellen en doorsturen, of via RSS-bridge)
```

> **Fase 1 → fase 2:** Items in NetNewsWire zijn nog niet opgeslagen — ze staan alleen in je feedlezer. Dit is bewust: je bladert erdoorheen en scant kopjes en intro's zonder direct te archiveren. Alleen wat echt relevant is ga je doorsturen naar de vault. Dat is het filtermoment.

**Van NetNewsWire naar de vault (fase 2 → fase 3):**

Interessante artikelen sla je op via twee routes:

- **Via Zotero browser-extensie of iOS-app:** open het artikel, klik op het Zotero-icoon → item wordt met metadata opgeslagen in Zotero `_inbox`. Gebruik deze route voor academische artikelen waarbij je BibTeX-metadata en annotatiemogelijkheden wilt bewaren.
- **Direct naar `inbox/`:** geef de URL aan Claude Code met de instructie `inbox [URL]` → Claude Code haalt de inhoud op en slaat het op als Markdown-bestand in `inbox/`, zonder Zotero. Gebruik deze route voor niet-academische artikelen, nieuwsberichten en beleidsdocumenten.

> **Privacy-noot:** NetNewsWire slaat feed-data lokaal op. Er worden geen leesgewoonten verstuurd naar externe servers.

### 12b. Academische feeds: van NetNewsWire naar Zotero

Voor academische artikelen uit NetNewsWire is de aanbevolen route om ze altijd eerst toe te voegen aan Zotero voordat je ze laat verwerken. Zo heb je BibTeX-metadata en annotatiemogelijkheden beschikbaar:

1. Open het artikel vanuit NetNewsWire in je browser
2. Klik op het Zotero-icoon in je browser (of gebruik de Zotero iOS-app) → item wordt opgeslagen in `_inbox`
3. Verwerk vanuit `_inbox` via type 0 → type 1 in de skill

---

## Stap 13: Spaced repetition (Obsidian plugin)

De Obsidian Spaced Repetition plugin gebruikt het SM-2-algoritme om flashcards te plannen op basis van hoe goed je ze kent. Kaarten worden aangemaakt in je Markdown-bestanden en beoordeeld binnen Obsidian.

### 13a. Plugin installeren

1. Open Obsidian
2. Ga naar **Instellingen → Community plugins → Community plugins bladeren**
3. Zoek op "Spaced Repetition"
4. Installeer de plugin van Stephen Mwangi
5. Schakel de plugin in via de toggle

### 13b. Flashcard-formaat

Kaarten worden aangemaakt in gewone Markdown-bestanden met behulp van het `?`-scheidingsteken:

```markdown
#flashcard

Wat is de definitie van substitutiezorg?
?
Zorg die verplaatst wordt van de tweede naar de eerste lijn, met behoud van kwaliteit maar lagere kosten.

Welke drie pijlers heeft het Integraal Zorgakkoord?
?
1. Passende zorg
2. Samenwerking in de regio
3. Digitalisering en gegevensuitwisseling
```

Kaarten kunnen in dezelfde file staan als de literatuurnotitie of worden weggeschreven naar `flashcards/`. De aanbevolen aanpak is om kaarten **in de notitie zelf** te plaatsen: zo blijft de kaart verbonden aan haar context en bronvermelding, en kun je bij het reviewen direct zien waar een concept vandaan komt. De `flashcards/` map is bedoeld voor zelfstandige conceptkaarten die niet aan één specifieke bron gebonden zijn — bijvoorbeeld definities of principes die je los van een paper wilt onthouden.

### 13c. Claude Code genereert flashcards automatisch

Na het aanmaken van een literatuurnotitie kun je Claude Code vragen om flashcards te genereren:

```
Maak 3–5 flashcards voor de zojuist gemaakte literatuurnotitie. 
Gebruik het Obsidian Spaced Repetition formaat met ? als scheidingsteken.
```

Claude Code voegt de kaarten toe aan het einde van de bestaande note (of schrijft ze naar `flashcards/[zelfde naam].md`).

### 13d. Dagelijkse review

1. Open Obsidian
2. Klik op het kaartpictogram in de rechterzijbalk (of gebruik `Cmd + Shift + R`)
3. Beoordeel de kaarten die vandaag gepland zijn: **Makkelijk / Goed / Moeilijk**
4. De plugin plant de volgende review automatisch op basis van je beoordeling

> **Privacy-noot:** Alle kaarten en review-data worden opgeslagen als lokale bestanden in je vault. Er is geen cloud-sync vereist.

---

## Stap 14: Filterlaag inrichten per bron

Dit is de kern van het 3-fasen model: fase 2, het filtermoment, is voor elke bron anders ingericht. Hieronder staat per bron wat de dump-laag is, wat het filtermoment is, en hoe je doorgeeft wat de vault in mag.

### Papers (Zotero)

| Fase | Wat |
|------|-----|
| Dump-laag | Zotero `_inbox` collectie — centrale verzamelbucket voor alle bronnen |
| Filtermoment | Abstract lezen in Zotero, of Claude Code laten samenvatten via Qwen3.5:9b (lokaal) |
| Go | Item verplaatsen naar de relevante collectie in je bibliotheek |
| No-go | Item verwijderen uit `_inbox` — er wordt geen notitie aangemaakt |

**Taggebaseerde filterlogica**

Claude Code past de beoordeling aan op basis van de Zotero-tag van het item:

| Tag | Behandeling |
|-----|------------|
| `✅` | Al eerder goedgekeurd — sla Go/No-go over, ga direct naar verwerking |
| `📖` | Als interessant gemarkeerd — stel alleen de Go/No-go vraag, geen samenvatting |
| `/unread`, geen tag, of een andere tag | Genereer samenvatting + relevantie-indicatie, vraag Go of No-go |

Items met onbekende tags (bijv. eigen projecttags of type-aanduidingen) worden dus behandeld als `/unread`: Claude Code genereert een samenvatting en vraagt om een Go/No-go beslissing.

**No-go is altijd definitief:** een afgewezen item wordt verwijderd uit `_inbox` en krijgt geen notitie in de vault. Claude Code vraagt altijd bevestiging vóór verwijdering.

Claude Code kan je helpen bij de beoordeling — vraag een samenvatting van items in `_inbox`:

```
Geef me een overzicht van de items in mijn Zotero _inbox collectie met per item 
een samenvatting van 2-3 zinnen en een relevantie-oordeel voor mijn onderzoek 
naar [thema].
```

Claude Code haalt via Zotero MCP de metadata en abstract op, en geeft per item een advies. Jij beslist vervolgens welke items de volgende stap verdienen.

### YouTube-video's

| Fase | Wat |
|------|-----|
| Dump-laag | Zotero `_inbox` via iOS share sheet vanuit de YouTube-app |
| Filtermoment | Eerste 5–10 minuten bekijken, of Claude Code laten samenvatten op basis van metadata |
| Go | `transcript [URL]` in Claude Code |
| No-go | Item verwijderen uit `_inbox` |

### Podcasts

| Fase | Wat |
|------|-----|
| Dump-laag | Zotero `_inbox` via iOS share sheet vanuit Overcast (overcast.fm-URL) |
| Filtermoment | Eerste 5–10 minuten beluisteren |
| Go | `podcast [URL]` in Claude Code (download + transcriptie + verwerking) |
| No-go | Item verwijderen uit `_inbox` |

Voor podcasts is het filtermoment bewust handmatig — audio is minder snel te beoordelen dan een abstract. Je kunt Claude Code wel vragen de shownotities van een aflevering op te halen als extra hulp bij de beslissing:

```
Haal de shownotities op van [URL] en geef een samenvatting van 3 zinnen.
```

### RSS-feeds

| Fase | Wat |
|------|-----|
| Dump-laag (academisch én niet-academisch) | NetNewsWire — ongelezen items |
| Filtermoment | Koptekst en intro scannen |
| Go (academisch) | Artikel openen → opslaan in Zotero via browser-extensie of iOS-app → komt in `_inbox` terecht |
| Go (niet-academisch) | Via Zotero Connector opslaan, of `inbox [URL]` doorgeven aan Claude Code |
| No-go | Item als gelezen markeren of verwijderen uit NetNewsWire |

### Workflow-overzicht in één oogopslag

```
FASE 1 — DUMP (bronnen → _inbox)     FASE 2 — FILTER           FASE 3 — VERWERKEN
──────────────────────────────────    ──────────────────────    ──────────────────────
Browser (Connector/iOS)  ──┐
NetNewsWire RSS          ──┤
Overcast (iOS share)     ──┼──► Zotero _inbox ──► Qwen3.5:9b samenvatting ──► Claude Code + vault
YouTube (iOS share)      ──┤                      Jouw Go/No-go
Overig (iOS share)       ──┘
                                   ↓ No-go: verwijderen uit _inbox
```

---

## De research workflow skill activeren

De skill is een markdown-bestand dat Claude Code vertelt hoe het zich moet gedragen tijdens research-sessies. Eenmalige installatie:

```bash
# Maak de skills-map aan in je vault
mkdir -p ~/Documents/ResearchVault/.claude/skills

# Kopieer het skill-bestand naar de vault
cp research-workflow-skill.md ~/Documents/ResearchVault/.claude/skills/
```

Voeg daarna de volgende regel toe aan je `CLAUDE.md` (onderaan):

```markdown
## Actieve skills
- Lees en volg `.claude/skills/research-workflow-skill.md` bij elke research-sessie.
```

Vanaf dat moment is de skill actief zodra je Claude Code opent in je vault. Je kunt de workflow starten door te typen: `/research` of simpelweg "start research workflow".

---

## Dagelijkse workflow na installatie

Zodra alles is ingesteld, is de dagelijkse workflow eenvoudig:

1. **Start Zotero** (zodat de lokale API actief is)
2. **Open Terminal in je vault:** `cd ~/Documents/ResearchVault && claude`
3. **Activeer de skill:** typ `/research` of "start research workflow"
4. Claude Code stelt een intakevraag en begeleidt je van daaruit interactief

Je hoeft niet precies te weten wat je zoekt — de skill is ontworpen om je daarbij te helpen.

---

## Probleemoplossing

| Probleem | Mogelijke oorzaak | Oplossing |
|---|---|---|
| Zotero MCP geeft geen resultaten | Zotero staat niet open | Start Zotero en controleer `http://localhost:23119/` |
| Lokale API niet beschikbaar | Instelling niet aangevinkt | Zotero → Instellingen → Geavanceerd → lokale API inschakelen |
| `zotero-mcp` niet gevonden | uv-pad niet in shell | Voeg `~/.local/bin` toe aan `$PATH` in `~/.zshrc` |
| Semantisch zoeken geeft geen resultaten | Database niet geïnitialiseerd | Run `zotero-mcp update-db` |
| Claude Code ziet de MCP-tool niet | Configuratiebestand ontbreekt | Controleer `~/.claude/claude_desktop_config.json` |
| Ollama reageert niet | Service niet gestart | Run `ollama serve` of `brew services start ollama` |
| yt-dlp geeft geen ondertitels | Video heeft geen (auto-)ondertitels | Probeer `--sub-lang en` of controleer of de video überhaupt ondertitels heeft |
| launchd-update draait niet | Zotero staat niet open op het geplande tijdstip | Start Zotero handmatig en run `update-zotero`, of kies "Auto on startup" in stap 10c optie 1 |
| whisper-cpp geeft foutmelding | Model nog niet gedownload | Wacht op eerste download, of check schijfruimte |
| Whisper-transcriptie is onnauwkeurig | Audioqualiteit laag of taaldetectie onjuist | Gebruik `--model medium` voor betere kwaliteit, of geef taal expliciet op met `--language nl` of `--language en` als automatische detectie de verkeerde taal kiest |
| NetNewsWire synchroniseert niet | Geen sync ingesteld (lokaal werkt altijd) | NetNewsWire werkt standaard lokaal; iCloud-sync is optioneel |
| Obsidian flashcards verschijnen niet | Plugin niet ingeschakeld | Instellingen → Community plugins → Spaced Repetition aanzetten |
| Flashcards worden niet herkend | Verkeerd formaat | Controleer of `?` op een eigen regel staat en `#flashcard` aanwezig is |

---

## Privacy-overzicht van de volledige stack

| Component | Data lokaal? | Toelichting |
|---|---|---|
| Zotero + lokale API | ✅ Volledig | Draait op `localhost`, geen cloud |
| Zotero MCP | ✅ Volledig | Lokale verbinding, geen externe API |
| Obsidian vault | ✅ Volledig | Gewone bestanden op je Mac |
| Ollama + Qwen3.5:9b | ✅ Volledig | Model draait lokaal op M4; standaard voor alle verwerkingstaken |
| yt-dlp | ✅ Volledig | Scraping lokaal uitgevoerd |
| whisper.cpp | ✅ Volledig | Transcriptie lokaal op M4 via Metal |
| NetNewsWire | ✅ Volledig | RSS-data lokaal opgeslagen, geen account |
| Obsidian Spaced Repetition | ✅ Volledig | Kaarten en review-data in vault-bestanden |
| Claude Code — standaard | ✅ Volledig | Orchestratie en Zotero MCP-aanroepen; Qwen3.5:9b doet het genereerwerk lokaal |
| Claude Code — `--hd` modus | ⚠️ Gedeeltelijk | Alleen bij expliciete `--hd` aanvraag: prompt én broninhoud gaan naar Anthropic API (Claude Sonnet 4.6) |

> **Conclusie:** in de standaardmodus verlaat geen vault-inhoud, paper, transcript of notitie de Mac mini. Claude Code orchestreert de workflow, maar het redeneer- en schrijfwerk gebeurt lokaal via Qwen3.5:9b. Alleen wanneer je expliciet `--hd` of "maximale kwaliteit" vraagt, gaat de broninhoud naar de Anthropic API. Claude Code vraagt dan altijd eerst om bevestiging.

---

*Installatiegids versie 1.11 — maart 2026*  
*Getest op Mac mini M4 (2024), 24 GB, macOS Sequoia*  
