---
name: model-evaluatie
user_invocable: true
description: >
  Protocol voor het vergelijken van LLM's voor de olw-backend (of een andere
  concept-extractiepijplijn). Activeer bij "model bake-off", "welk model voor olw",
  "modellen vergelijken", "nieuw model testen", of /model-evaluatie. Bevat de opzet in
  rondes, de metrieken met hun valkuilen, en de controles die vooraf horen — afgeleid uit
  de bake-off van 14–16 aug 2026, waar vrijwel elke misstap vooraf te voorkomen was.
---

# Skill: model-evaluatie voor de olw-backend

## Het grondbeginsel

**Meet de fase waarin het probleem ontstaat.** In de bake-off van augustus 2026 wezen drie
rondes drie verschillende winnaars aan, uitsluitend doordat de metrieken naar verschillende
fasen keken. De vraag was of Nederlandse en Engelse bronnen op één conceptpagina landen; de
hoofdmetriek mat alleen wat modellen met Nederlandse bronnen deden. Dat gaf een model 100%
terwijl het bij de Engelse bronnen een parallelle graaf bouwde.

Formuleer dus eerst: *waar in de pijplijn ontstaat het gedrag dat ik wil beoordelen?* Bij
olw geldt:

| gedrag | ontstaat in | model |
|---|---|---|
| conceptnamen, taalkeuze, fragmentatie | `ingest` | **fast** |
| artikelteksten, wikilinks, synthese | `compile` | **heavy** |
| artikeltaal (niet de namen) | `compile` | via `pipeline.language` |

## Rondestructuur

Vier rondes, oplopend in kosten. Elke ronde mag de volgende afblazen.

### Ronde 0 — rooktest (10 min per model)
Twee kleine bundels, één ingest, één compile-probe met tijdslimiet. Beantwoordt:
levert het model bruikbare JSON volgens olw's schema, en hoeveel seconden per 1000 woorden?
Modellen die hier nul concepten opleveren vallen af vóór ze uren kosten.

**Controleer `ollama show <model>` op de capability `thinking`.** Thinking-modellen
(qwen3.5) leveren onder `format=json` een denkblok en stoppen daarna —
"model returned no usable content (finish_reason=stop)", nul concepten. Oplossing: de proxy
`nothink_proxy.py` naast deze skill, die `"think": false` injecteert:

```
python3 .claude/skills/model-evaluatie/nothink_proxy.py 11435
olw --provider-url http://localhost:11435 ...
```

**Meet prefill en generatie apart.** Eén getal "seconden per 1000 woorden" verbergt dat de
twee fasen aan verschillende grenzen hangen. Generatie is bandbreedte-gebonden en schaalt
lineair met de residente modelgrootte; prefill is compute-gebonden en zakt veel sneller weg
naarmate het model groeit. Bij bundelverwerking, waar de invoer lang is en de uitvoer kort,
bepaalt prefill de looptijd — precies de fase die een generatie-benchmark niet ziet.

Neem de cijfers uit de engine zelf, niet uit een stopwatch. `/api/generate` met
`stream=false` geeft `prompt_eval_count`/`prompt_eval_duration` en
`eval_count`/`eval_duration`; daaruit volgen beide snelheden los van elkaar. Doe per model
eerst een koude load (`ollama stop`, dan één token genereren) zodat laadtijd niet in de
meting lekt, en controleer met `ollama ps` dat `PROCESSOR` 100% GPU is — een model dat
gedeeltelijk naar de CPU uitwijkt levert een getal dat nergens op slaat.

Reken de effectieve bandbreedte terug: `generatie_t/s × residente_GB`. Ligt die over alle
modellen binnen een smalle band, dan is de machine bandbreedte-gebonden en voorspelt
`generatie_t/s ≈ effectieve_bandbreedte / residente_GB` de modellen die je niet hebt getest.
Dat scheelt een ronde. De gemeten waarden voor deze installatie staan in
`ResearchVault-plans/RUNBOOK.md`; ze zijn machine-specifiek en horen niet in dit handboek.

### Ronde 1 — screening (ingest-only)
Alle kandidaten, één run. **Geen compile**: metriek A2, F, G en H komen uit de
`concepts`-tabel die `ingest` vult. Compile kost 60–70% van de looptijd en levert de
screening niets. Dat verschil is 7 uur tegen 20.

### Ronde 2 — bevestiging (ingest-only, 3 runs per model)
**Herhalingen zijn niet optioneel.** De extractie is aantoonbaar niet-deterministisch: één
model gaf op identieke invoer 23, 8 en 10 seed-concepten. Eén run per model kan modelverschil
niet van runvariatie onderscheiden — en de screening wees daardoor een winnaar aan die het
niet was.

### Ronde 3 — `olw compare` (mét compile)
Champion tegen challenger, met een `queries.toml`. **Zonder queries geeft compare altijd
`manual_review`** (`compare/metrics.py`: `if not report.query_diffs`). Query-scores wegen
bovendien zwaarder dan alle structuurmetrieken samen: één regressie kleiner dan −0,10
blokkeert een switch.

## Vaste controles

**Valideer het scorescript op bekende data vóór de eerste echte run.** Draai het op een
eerdere bake-off waarvan je de uitkomst kent. Reproduceert het die niet, dan deugt het script
niet — tien minuten die uren beschermen.

**Face-validity door de onderzoeker, als vaste stap.** Lees drie gegenereerde pagina's per
conditie. In augustus keerde dit de conclusie: het model met de meeste concepten bleek
legitieme begrippen aan te dragen die de "winnaar" miste, en de winnaar bleek aparte
begrippen samen te proppen als aliassen. Metrieken zien naamgeving, geen inhoud.

**Controleer of de tool je configuratie overneemt.** `olw compare` schrijft een eigen
`wiki.toml` in de efemere vault en neemt daarin alleen `auto_*`, `watch_debounce`,
`max_concepts_per_source`, `ingest_parallel` en `language` over. `article_max_tokens` en
`concept_draft_soft_cap` vallen terug op defaults — je instelling wordt genegeerd. Lees
`_write_effective_compare_toml` vóór je iets configureert, niet erna.

## Metrieken en hun valkuilen

| | wat | valkuil |
|---|---|---|
| **A2** | Engelse paginanaam waar de canon een NL-naam kent | kleine noemer in verse vaults; pas bruikbaar als er canon is opgebouwd (dus ronde 3) |
| **H** | aandeel NL-namen uit uitsluitend NL-bronnen | meet de verkeerde fase als de vraag over EN-bronnen gaat; nooit rapporteren zonder noemer — 100% over 8 concepten ≠ 100% over 44 |
| **G** | twee namen voor één begrip binnen één run | bewerkingsafstand ≤ 2 markeert ook betekenis*omkeringen*: `Illegitimate/Legitimate Risk Adjusters`, `N-type/S-type`, `C-variable/R-variable`. Guard nodig op ontkennende voorvoegsels en categoriecodes |
| **D′** | foutvormen | detecteer op vorm, niet alleen op een lijst: twee namen in één titel, dubbele spaties, opsommingslabels (`Doel A`) |
| **E** | aliaskwaliteit | **onderschat** — bleek achteraf het scherpste onderscheid. Machinaal detecteerbaar: een alias die een strikt prefix is van zijn eigen conceptnaam (`risk eq`, `risk equalizat`) is per definitie geen synoniem |
| — | synthesebreedte | aantal bronnen per conceptpagina onderscheidt kennisartikel (8 bronnen) van bronsamenvatting (2). Betere kwaliteitsmaat dan conceptaantal |

Bij taaldetectie op conceptnamen: exacte woordvergelijking mist **Nederlandse
samenstellingen** — `poliskenmerken`, `doelmatigheidsprikkel`. Gebruik substring-matching op
de canon-woordenschat. En `in` is in beide talen een functiewoord; die hoort in geen enkele
markerlijst.

## Een meting is een project, geen bijproduct van de vault

Deze sectie schreef tot 5 sep 2026 het omgekeerde voor: bewaar de meetopzet bij de instance,
gooi het gereedschap weg. Dat bleek fout, en de manier waarop het fout ging is de les.

Het harnas leefde als wegwerpmap in de vault, de meetopzet ernaast in een instance-map, en de
ruwe runs weer ergens anders — drie regimes voor één meting, geen daarvan met een backuplaag.
In vier weken verhuisde dat materiaal vier keer, en elke verhuizing riep dezelfde vraag opnieuw
op. De oorzaak was niet de indeling maar de aanname: dat een meting een bijproduct van de vault
is. Dat is ze niet. Ze **gebruikt** de vault als meetobject, zoals andere projecten de
bibliotheek als bron gebruiken.

Vuistregels die daaruit volgen:

- **Eén repo per onderzoeksvraag**, met de vraag, de methode en het verdict in de `README`. De
  meetopzet hoort daar ook in: zonder de bundelselectie en de query-set is een uitslag niet na
  te vertellen.
- **Code importeert, kopieert niet.** Meet je wat de productie doet, gebruik dan de
  productieconstanten uit de vault — een kopie meet vanaf dat moment een systeem dat niet meer
  bestaat.
- **Broninhoud blijft buiten elke remote**, ook een privé. Gelabelde grondwaarheid met titels en
  abstracts hoort in een gitignored `data/` met een eigen backupregel.
- **Gitignored is geen backup.** Een nieuwe gitignore-regel voor afgeleide data is een stil gat
  tot er een expliciete `rclone`-regel bij staat.
- **Bouw een poort.** Een script dat een eerder bekende uitslag reproduceert is een
  regressietest op het meetinstrument, en de goedkoopste manier om te merken dat een
  verplaatsing of een constante iets heeft verschoven.

De uitwerking voor deze vault staat in de privé-repo `ResearchVault-metingen`; het besluit in
`ResearchVault-plans`, ADR-0011.

## Bekende valkuilen bij het schrijven van de runner

- **Merge-sleutels symmetrisch houden.** Twee keer misgegaan: schrijven op `model#run` en
  lezen op `model` vouwt herhalingen samen tot de laatste — precies de variantie waarvoor
  ronde 2 bestaat. Lees- en schrijfsleutel horen uit dezelfde expressie te komen.
- **Parameternamen die functies schaduwen.** `def conditie(..., run: int)` maakte de
  functie `run()` onbereikbaar. Een droogloop vangt dit niet: die stopt vóór de uitvoering.
  Verifieer met één echte aanroep op één bundel.
- **`timeout` in de Bash-tool is milliseconden, maximaal 600000** — tien minuten. Werk dat
  langer duurt hoort onder `nohup` + `disown`, anders kapt de tool het af.
- **Controleer de woordentelling na `build-zotero-bundle.py`.** Een bundle van 2 woorden
  ziet er in `raw/` normaal uit en levert stil nul concepten. De guard meldt dit sinds
  15 aug 2026 als status `leeg`.

## Operationele randvoorwaarden

- **`touch ~/.no-autoshutdown`** vóór een lange run; guard #6 beschermt lopende
  `olw ingest|compile` maar niet de pauzes ertussen. **Verwijder hem na afloop** — zolang
  hij staat sluit de Mac niet af, en daarmee draait ook de ochtendbatch niet (die hangt aan
  de login-cyclus), en dus de Proton-backup niet.
- **Overdagtaken pauzeren** met `mkdir /tmp/overdagtaken.lock` — dezelfde mutex die het
  script zelf gebruikt, dus geen sudo nodig. Zet hem pas als er geen run actief is: de trap
  van een lopende run ruimt hem anders op. `rmdir` na afloop.
- **Modelwissels**: `ollama stop` tussen condities. Op 24 GB passen geen twee grote modellen
  tegelijk; `fast = heavy` voorkomt swap-thrash.
- **Schijfruimte**: `ollama rm` geeft ruimte pas vrij na
  `sudo tmutil thinlocalsnapshots / <bytes> 4` — APFS-snapshots houden de blocks vast, en
  `du` en `df` lopen dan uiteen. Controleer met `df -h ~/.ollama/models`.

## Wat je niet uit benchmarks haalt

Gepubliceerde scores zijn niet onderling vergelijkbaar: `bge-m3` scoorde 69,2 op MIRACL in
Nomic's tabel, `granite-embedding-r2` 59,8 in IBM's eigen paper — andere opzet, andere talen,
andere belangen. In de E2-meting op eigen materiaal won `nomic-embed-text-v2-moe` (62% top-1)
van `bge-m3` (52%), tegen die scores in. Meet op je eigen corpus, met je eigen begrippen.

**En absolute gelijkenis is geen kwaliteitsmaat.** In een meting van 21 aug 2026 op korte
Nederlandse teksten gaf `granite-embedding:278m` de hóógste cosine-waarden (mediaan 0,609,
sd 0,035) en rangschikte het de bekend-relevante items het slechtst; `bge-m3` lag in absolute
zin veel lager (mediaan 0,400) en rangschikte het best. Modellen spreiden de ruimte
verschillend — een hoge cosine kan anisotropie zijn in plaats van gelijkenis. Vergelijk
embedders dus op de rangorde van bekend-relevante items, nooit op een drempelwaarde.

Let daarbij ook op de **aggregatie**, niet alleen op het model: een profiel dat het gemiddelde
is van duizenden vectoren ligt dicht bij het zwaartepunt van de embeddingruimte, en gelijkenis
met een zwaartepunt meet genericiteit. In dezelfde meting wonnen programma's met de titel
"Pause" en "Weather". Toets dat artefact vóór de modelvergelijking — anders rapporteer je het
als modelverschil.
