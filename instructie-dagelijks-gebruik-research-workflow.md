**1. Mac mini aanzetten**

**2. Zotero starten**

**3. Terminal openen en naar je vault navigeren**
>cd ~/Documents/ResearchVault
>claude
```
Dit start Claude Code in de context van je vault, zodat het je `CLAUDE.md` en de research workflow skill oppikt.

**3. De skill activeren**
Typ in Claude Code:
```
>/research 
```
of gewoon: `start research workflow`

**4. De inbox-beoordeling starten**
Kies optie `0` uit het workflow-menu, of typ direct:
```
>beoordeel inbox
```
Claude Code haalt via Zotero MCP alle items op uit je `_inbox` collectie en geeft per item een samenvatting van 2–3 zinnen plus een relevantie-oordeel. Jij geeft per item **Go** of **No-go**.

**5. Afhandeling per beslissing**
- **Go:** Claude Code verplaatst het item naar de juiste collectie in Zotero en maakt een literatuurnotitie aan in `literature/`
- **No-go:** Claude Code verwijdert het item uit `_inbox` (na jouw bevestiging)

**6. Afsluiten**
Claude Code sluit af met een overzicht: X items goedgekeurd, Y verwijderd. Daarna kun je nog vragen of de Zotero-zoekdatabase bijgewerkt moet worden als er nieuwe papers zijn goedgekeurd:
```
>update database

**4. Mac mini uitzetten**
