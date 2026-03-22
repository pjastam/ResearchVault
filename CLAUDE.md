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
---
```

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

## Actieve skills
- Lees en volg `.claude/skills/research-workflow-skill-v1.12.md` bij elke research-sessie.