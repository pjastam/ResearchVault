---
name: wrap-up
user_invocable: true
description: >
  End-of-session documentation sync followed by git commit + push to GitHub.
  Triggers automatically when the user says "update github", "push naar github",
  "sync naar github", "commit en push", or similar end-of-session phrases.
  Detects which files changed, updates only the affected documentation sections,
  then commits all changes and pushes.
---

# Skill: Wrap-up — docs sync + GitHub push

## Wanneer deze skill actief is

Activeer deze skill wanneer de gebruiker een van de volgende formuleringen gebruikt
(of varianten daarop):

- "update github"
- "push naar github"
- "sync naar github"
- "commit en push"
- "sla op naar github"
- `/wrap-up`

Voer **altijd** stap 1 t/m 3 uit vóórdat je git-commando's uitvoert.

---

## Stap 1 — Detecteer wijzigingen

```bash
git -C ~/Workspace/repos/GitHub/ResearchVault diff --stat HEAD
git -C ~/Workspace/repos/GitHub/ResearchVault status --short
```

Verwerk de output in een mentale lijst van gewijzigde bestanden. Sla deze stap over als
de working tree schoon is — ga dan direct naar stap 3 voor eventuele al-gestagede
wijzigingen.

---

## Stap 2 — Docs bijwerken op basis van gewijzigde bestanden

Gebruik de onderstaande mapping om te bepalen welke docs bijgewerkt moeten worden.
Werk **alleen** de docs bij die relevant zijn voor de daadwerkelijk gewijzigde bestanden.
Lees vóór elke update de huidige sectie zodat je gericht aanvult of corrigeert.

### Mapping: gewijzigd bestand → bij te werken doc

| Gewijzigd bestand | Bij te werken documentatie |
|---|---|
| `.claude/process_item.py` | `CLAUDE.md` § Ingest-procedure + `docs/src/usage/phase3-process.md` |
| `.claude/summarize_item.py` | `CLAUDE.md` § Ingest-procedure + `docs/src/usage/phase3-process.md` |
| `.claude/fetch-fulltext.py` | `CLAUDE.md` § Privacyregel + `docs/src/reference/daily-workflow.md` |
| `.claude/ollama-generate.py` | `docs/src/reference/daily-workflow.md` |
| `.claude/attach-transcript.py` | `CLAUDE.md` § YouTube-transcripten + `docs/src/usage/phase3-process.md` |
| `.claude/index-score.py` | `CLAUDE.md` § _inbox prioritering + `docs/src/usage/phase2-filter.md` |
| `.claude/feedreader-score.py` | `CLAUDE.md` § Feedreader + `docs/src/usage/phase1-sources.md` |
| `.claude/feedreader-learn.py` | `CLAUDE.md` § Feedreader (leerloop) + `docs/src/usage/phase1-sources.md` |
| `.claude/feedreader-server.py` | `CLAUDE.md` § Feedreader (URLs) |
| `.claude/feedreader_core.py` | `CLAUDE.md` § Feedreader (constanten/scores) |
| `.claude/freshrss_utils.py` | `CLAUDE.md` § Feedreader (FreshRSS-setup) |
| `.claude/zotero-inbox.py` | `CLAUDE.md` § Zotero-hulpscripts |
| `.claude/zotero-remove-from-inbox.py` | `CLAUDE.md` § Zotero-hulpscripts |
| `.claude/zotero_utils.py` | `CLAUDE.md` § Zotero-hulpscripts |
| `.claude/skills/SKILL.md` | `docs/src/reference/daily-workflow.md` |
| `~/bin/nachtelijke-taken.sh` | `~/bin/RUNBOOK.md` |
| `~/bin/overdagtaken.sh` | `~/bin/RUNBOOK.md` |
| `~/bin/proton-*.sh` | `~/bin/RUNBOOK.md` |
| Nieuw `.py`-bestand in `.claude/` | Voeg toe aan `CLAUDE.md` § Zotero-hulpscripts of § Feedreader (afhankelijk van functie) |
| `/Library/LaunchDaemons/*.plist` | `~/bin/RUNBOOK.md` § Overzicht geplande taken |

### Werkwijze per doc-update

1. Lees de huidige relevante sectie in het doelbestand
2. Lees de git-diff van het gewijzigde bronbestand (`git diff HEAD -- <bestand>`)
3. Bepaal wat er inhoudelijk is veranderd (nieuwe parameters, gewijzigd gedrag, nieuwe bestanden)
4. Schrijf alleen de gewijzigde onderdelen bij — herschrijf de volledige sectie niet tenzij nodig
5. Meld per doc: "✓ `CLAUDE.md` § Feedreader bijgewerkt — Bayesiaanse drempelwaarden aangepast"

### Als de wijziging onduidelijk is

Als de diff niet volstaat om te begrijpen wat er veranderd is, vraag dan één gerichte vraag:
"Wat is er in deze sessie inhoudelijk veranderd aan `[bestand]`?" — en werk daarna pas de doc bij.

---

## Stap 3 — Commit + push

Na afronding van alle doc-updates:

```bash
cd ~/Workspace/repos/GitHub/ResearchVault
git add -A
git status
```

Toon de git-status en vraag om bevestiging van het commit-bericht vóór je commit.
Stel zelf een beknopt commit-bericht voor op basis van de wijzigingen.

Na bevestiging:

```bash
git commit -m "[voorgesteld bericht]"
git push
```

---

## Uitzonderingen

- **Geen wijzigingen:** als `git status` een schone working tree toont én er niets te pushen is, meld dan: "Working tree schoon, niets te committen."
- **Alleen doc-wijzigingen:** als alleen docs zijn bijgewerkt (geen bronbestanden), sla dan stap 2 over en ga direct naar stap 3.
- **`~/bin/`-bestanden:** die liggen in een **aparte git-repo** (`github.com/pjastam/bin`), niet in de ResearchVault-repo. "Apart beheerd" betekent níet "buiten git" — commit + push ze dáár met `git -C ~/bin status/commit/push`, en gebruik géén `git add` voor die bestanden in ResearchVault. Meld dat `RUNBOOK.md` + `~/bin/`-scripts in hun eigen repo zijn bijgewerkt.
