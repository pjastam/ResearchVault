"""
feedreader_labels.py — Labellogica van de leerloop
===================================================
Pure functies over logregels uit ``score_log.jsonl``. Geen I/O, geen netwerk,
alleen stdlib — zodat de tests op een kale CI-runner draaien, net als
``feedreader_fetch.py`` en ``feedreader_identity.py``.

**Waarom deze module bestaat.** De labellus zat in ``feedreader-learn.py``, en dat
bestand draagt een hyphen en is dus niet importeerbaar. Daardoor was de kern van
de leerloop de enige onteste laag van de pijplijn — en precies daar bleven drie
signalen maandenlang dood zonder dat iemand het merkte.

**Wat de auto-ster-markering repareert.** ``feedreader-score.py`` zet elk item met
score ≥ ``THRESHOLD_STAR`` in de star-queue; ``feedreader-learn.py`` sterrt die in
FreshRSS en haalt in *dezelfde run* de gesterde set weer op, waarna de labellus ze
als positief labelt. Meting van 19 aug 2026: van de 1.923 positieven kwamen er
1.816 uit de ster, en 1.815 daarvan lag op of boven de drempel. Precies één lag
eronder (score 65). Het drempeladvies rustte dus grotendeels op zelfbevestiging en
kwam niet toevallig uit op ongeveer de drempel die het al had.

De labels worden **niet** vernietigd — de gesterde stream is gecapt op 1.000 items
en dat is niet terug te draaien. Ze worden gemarkeerd en uitgesloten uit het advies.
"""

from feedreader_identity import canonical_url

# Kandidaat-drempels voor het THRESHOLD_STAR-advies.
STAR_CANDIDATES = tuple(range(40, 91, 5))

# Hoeveel beter dan willekeurig een drempel minimaal moet zijn voordat hij
# aanbevolen wordt. Bewust arbitrair, maar expliciet arbitrair: het volledige
# lift-verloop wordt eronder getoond zodat de keuze te overrulen is. 2,5× is
# gekozen omdat de score onder ~65 een lift van hooguit 1,2× haalt (gemeten
# 19 aug 2026) — dat is niet te onderscheiden van willekeurig sterren.
STAR_LIFT_TARGET = 2.5

# Onder dit aantal Zotero-treffers boven de drempel is de schatting te dun voor
# een getal. Liever geen advies dan valse precisie.
MIN_HITS_FOR_ADVICE = 30


def _entry_keys(entry):
    """Sleutelvormen waaronder een logregel bekend kan zijn: identity én canonieke URL.

    Twee vormen, om dezelfde reden als ``feedreader_identity.item_keys``: het
    ``identity``-veld bestaat alleen op regels van ná 16 aug 2026, dus de canonieke
    URL draagt de historie.
    """
    keys = set()
    ident = entry.get("identity")
    if ident:
        keys.add(ident)
    url = canonical_url(entry.get("url", ""))
    if url:
        keys.add(url)
    return keys


def apply_skips(entries, skips):
    """Markeert logregels die expliciet zijn afgewezen (👎).

    Matcht op identity vóór URL, net als de rest van de pijplijn sinds
    16 aug 2026. Dat is nodig voor podcastfeeds die bij elke aflevering dezelfde
    showpagina als link geven: op alleen de URL zou één 👎 de hele show raken.

    Geeft ``(aantal_gemarkeerd, niet_gematchte_skips)`` terug. Die tweede bestaat
    omdat de skip-queue onvoorwaardelijk geleegd wordt: zonder dit verdwijnt een
    👎 dat nergens op past geruisloos, en ziet de uitvoerregel eruit als een
    rustige dag. Dat is exact het maskeringspatroon dat de leerloop al drie keer
    eerder heeft getroffen.
    """
    gezocht = []
    for skip in skips:
        sleutels = set()
        if skip.get("identity"):
            sleutels.add(skip["identity"])
        cu = canonical_url(skip.get("url", ""))
        if cu:
            sleutels.add(cu)
        if sleutels:
            gezocht.append([skip, sleutels, False])  # [skip, sleutels, geraakt]

    count = 0
    for entry in entries:
        keys = _entry_keys(entry)
        if not keys:
            continue
        for paar in gezocht:
            if keys & paar[1]:
                paar[2] = True
                if not entry.get("skipped"):
                    entry["skipped"] = True
                    count += 1
                break
    ongematcht = [paar[0] for paar in gezocht if not paar[2]]
    return count, ongematcht


def mark_auto_starred(entries, star_urls, threshold):
    """Markeert logregels die de pijplijn zélf gesterd heeft.

    Twee bronnen van bewijs:

    * de URL stond in de star-queue van deze run — hard bewijs;
    * de regel draagt een ster én scoort op of boven ``threshold`` — het
      historische geval, want de star-queue van toen bestaat niet meer.

    Die tweede regel is een gemeten benadering, geen zekerheid. Van de 1.816
    gesterde logregels op 19 aug 2026 lag er precies één onder de drempel.
    Handmatig sterren laat een andere verdeling achter dan dat: wie met de hand
    sterrt, raakt ook af en toe een 55.

    Eenrichting en idempotent: markeert alleen, verwijdert nooit. Regels met een
    expliciete afwijzing (``skipped``) worden overgeslagen — een 👎 blokkeert alle
    latere signalen (ADR-0005).

    Geeft het aantal nieuw gemarkeerde regels terug.
    """
    canon = {canonical_url(u) for u in star_urls}
    canon.discard("")
    count = 0
    for entry in entries:
        if entry.get("skipped") or entry.get("auto_starred"):
            continue
        url = canonical_url(entry.get("url", ""))
        uit_queue = bool(url) and url in canon
        historisch = (
            entry.get("starred_in_freshrss") is True
            and (entry.get("score") or 0) >= threshold
        )
        if uit_queue or historisch:
            entry["auto_starred"] = True
            count += 1
    return count


def split_positives(entries):
    """Splitst de positieven in menselijk oordeel en zelfbevestiging.

    Geeft ``(echt, auto)`` terug. Alleen ``echt`` hoort in het drempeladvies: een
    advies dat op auto-sterren rust, adviseert de drempel die het al had.

    Een expliciet afgewezen regel (``skipped``) telt in geen van beide — het 👎
    wint van elk afgeleid signaal, ook van een ster die je met de hand zette.
    """
    echt, auto = [], []
    for entry in entries:
        if entry.get("skipped"):
            continue
        if entry.get("added_to_zotero") is not True:
            continue
        (auto if entry.get("auto_starred") else echt).append(entry)
    return echt, auto


def star_threshold_report(rows, candidates=STAR_CANDIDATES,
                          lift_target=STAR_LIFT_TARGET,
                          min_hits=MIN_HITS_FOR_ADVICE):
    """Evidentie-tabel voor `THRESHOLD_STAR`: wat levert elke drempel op?

    **Positief is de Zotero-match (`zotero_hit`), niet de ster.** De ster mag
    zichzelf niet beoordelen — precies de circulariteit die op 19 aug 2026 uit de
    leerloop is gehaald (ADR-0005). Elke rij is één artikel (ontdubbeld), met
    `score`, `zotero_hit` en eventueel `skipped`.

    Drie grootheden per kandidaat-drempel:

    * **precisie** — welk deel van wat je zou sterren, belandde in Zotero;
    * **dekking** — welk deel van alles wat in Zotero belandde, zou je sterren;
    * **lift** — precisie gedeeld door het basispercentage. 1,0 betekent: niet te
      onderscheiden van willekeurig sterren.

    De 👎-signalen leveren een **harde vloer** in plaats van een gewicht: geen
    drempel wordt aanbevolen die een expliciet afgewezen item zou sterren. Met 56
    waarnemingen (meting 19 aug 2026) draagt die klasse geen weging, maar wel een
    grens — en dat is het sterkste dat je ermee kunt doen.

    De timeout-negatieven doen hier bewust *niet* aan mee. Hun scoreverdeling ligt
    vrijwel over die van de positieven heen (AUC 0,585 tegen 0,771 voor de 👎's):
    "genegeerd" betekent overwegend "niet gezien", niet "niet interessant". Met
    10.859 tegen 56 rijen zouden ze het enige informatieve signaal 194 op 1
    overstemmen. De aanroeper hoort dat te melden in plaats van ze stil weg te
    laten.

    Geeft een dict met `basisrate`, `totaal`, `treffers_totaal`, `vloer`,
    `rijen` (per drempel) en `advies` + `reden`.
    """
    totaal = len(rows)
    treffers_totaal = sum(1 for r in rows if r.get("zotero_hit"))
    basisrate = treffers_totaal / totaal if totaal else 0.0

    skip_scores = [r.get("score", 0) for r in rows if r.get("skipped")]
    vloer = max(skip_scores) + 1 if skip_scores else None

    tabel = []
    for drempel in candidates:
        boven = [r for r in rows if r.get("score", 0) >= drempel]
        treffers = sum(1 for r in boven if r.get("zotero_hit"))
        precisie = treffers / len(boven) if boven else 0.0
        tabel.append({
            "drempel":  drempel,
            "gesterd":  len(boven),
            "treffers": treffers,
            "precisie": precisie,
            "dekking":  treffers / treffers_totaal if treffers_totaal else 0.0,
            "lift":     precisie / basisrate if basisrate else 0.0,
            "onder_vloer": vloer is not None and drempel < vloer,
        })

    advies, reden = _kies_drempel(tabel, vloer, lift_target, min_hits,
                                  treffers_totaal, basisrate)
    return {
        "basisrate":       basisrate,
        "totaal":          totaal,
        "treffers_totaal": treffers_totaal,
        "vloer":           vloer,
        "rijen":           tabel,
        "advies":          advies,
        "reden":           reden,
    }


def _kies_drempel(tabel, vloer, lift_target, min_hits, treffers_totaal, basisrate):
    """De laagste drempel boven de vloer die de lift én het minimum aantal haalt.

    De láágste, niet de beste: elke stap hoger kost dekking, en een gemiste ster
    is goedkoop omdat er niets wordt weggefilterd — het item staat gewoon in de
    gesorteerde feed. Zodra de lift gehaald is, is verder verhogen alleen nog
    verlies.
    """
    if not treffers_totaal or not basisrate:
        return None, "geen enkele Zotero-treffer in het logboek; niets om op te ijken"

    haalbaar = [r for r in tabel if not r["onder_vloer"] and r["lift"] >= lift_target]
    if not haalbaar:
        return None, (f"geen enkele drempel haalt een lift van {lift_target}× — "
                      f"de score onderscheidt hier te weinig")

    genoeg = [r for r in haalbaar if r["treffers"] >= min_hits]
    if not genoeg:
        beste = max(haalbaar, key=lambda r: r["treffers"])
        return None, (f"te weinig treffers boven de drempel ({beste['treffers']} < {min_hits}); "
                      f"de schatting is te dun voor een getal")

    keuze = min(genoeg, key=lambda r: r["drempel"])
    return keuze["drempel"], (f"laagste drempel boven de vloer met lift ≥ {lift_target}× "
                              f"en ≥ {min_hits} treffers")
