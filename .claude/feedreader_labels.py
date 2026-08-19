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
