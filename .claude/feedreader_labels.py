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
