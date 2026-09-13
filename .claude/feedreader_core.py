"""
feedreader_core.py — Gedeelde rekenkern voor de feedreader
===========================================================
Bevat puur rekenkundige hulpfuncties zonder I/O of feedparser-afhankelijkheden,
zodat ze herbruikbaar zijn vanuit feedreader-score.py, feedreader-learn.py en
toekomstige scripts.

De annotaties worden bewust niet op importtijd geëvalueerd (`from __future__ import
annotations`). Dit bestand noemt numpy in zijn signaturen, maar de meeste functies hier
rekenen zonder numpy — en test_zotero_utils.py leunt daarop met een lege nep-numpy om op
kale stdlib te kunnen draaien. Zonder deze regel evalueert Python ≤3.13 `np.ndarray` bij
het inlezen van de module en klapt die import eruit; Python 3.14 doet dat uit zichzelf al
niet meer (PEP 649), waardoor de fout lokaal onzichtbaar bleef en alleen in CI opdook.
"""

from __future__ import annotations

import re

import numpy as np

THRESHOLD_GREEN  = 50
THRESHOLD_YELLOW = 40
THRESHOLD_STAR   = 75  # items met score ≥ dit worden auto-gestefd in FreshRSS/NNW
                       # 70 → 75 op 19 aug 2026, op advies van feedreader-learn.py:
                       # lift 1,9× → 2,6× t.o.v. het basispercentage van 2,6%, ten koste
                       # van dekking (31,0% → 20,5%). Een gemiste ster is goedkoop — er
                       # wordt niets weggefilterd, het item staat in de gesorteerde feed.

PRIOR_RELEVANCE = 0.80  # a priori kans dat een item uit de geselecteerde feeds relevant is.
                        # 0.70 → 0.80 op 2 mei 2026 (33f968c), toen gemarkeerd als "tijdelijk
                        # voor testdoeleinden"; bevestigd op 23 aug 2026. Reden om te bevestigen
                        # en niet terug te draaien: THRESHOLD_STAR = 75 is op 19 aug 2026
                        # empirisch geijkt met een lift-analyse, en die draaide op scores die
                        # onder 0.80 zijn geproduceerd. Terugzetten maakt die ijking stil
                        # ongeldig. Het kantelpunt van bayesian_score() ligt op
                        # raw = (1-prior)*100, dus raw 20 in plaats van raw 30.

# Items with PDF annotations are treated as strong positive signals (3× weight vs. unannotated)
WEIGHT_DEFAULT     = 1
WEIGHT_ANNOTATIONS = 3


def cosine_similarity(vec: np.ndarray, profile: np.ndarray) -> float:
    norm = np.linalg.norm(vec)
    if norm == 0:
        return 0.0
    return float(np.dot(vec / norm, profile))


def compute_weighted_profile(
    embeddings: dict[str, np.ndarray],
    weights: dict[str, float],
) -> np.ndarray:
    vectors, w = [], []
    for key, emb in embeddings.items():
        vectors.append(emb)
        w.append(weights.get(key, WEIGHT_DEFAULT))
    matrix = np.stack(vectors)
    weights_arr = np.array(w, dtype=np.float32).reshape(-1, 1)
    profile = (matrix * weights_arr).sum(axis=0) / weights_arr.sum()
    norm = np.linalg.norm(profile)
    return profile / norm if norm > 0 else profile


def bayesian_score(raw: int, prior: float = PRIOR_RELEVANCE) -> int:
    """Bayesiaanse herweging van een ruwe cosine-score (0–100).

    Behandelt raw/100 als P(signaal | relevant) en (100-raw)/100 als
    P(signaal | niet-relevant). De prior codeert de verwachte relevantie
    van de geselecteerde feeds. Kantelpunt (Bayes = 50) ligt bij raw = (1-prior)×100.
    """
    s = raw / 100
    if s <= 0:
        return 0
    if s >= 1:
        return 100
    p = (s * prior) / (s * prior + (1 - s) * (1 - prior))
    return max(0, min(100, int(round(p * 100))))


def score_label(score: int) -> str:
    if score >= THRESHOLD_GREEN:
        return "🟢"
    elif score >= THRESHOLD_YELLOW:
        return "🟡"
    return "🔴"


def extract_snippet(text: str, max_len: int = 250) -> str:
    """Return first meaningful prose from a description, skipping link-heavy lines."""
    if not text:
        return ""
    prose = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        url_count = len(re.findall(r'https?://', line))
        word_count = len(line.split())
        if url_count >= 2 or (url_count == 1 and word_count <= 5):
            continue
        prose.append(line)
        if sum(len(l) for l in prose) >= max_len:
            break
    return " ".join(prose)[:max_len]


def make_item_summary(item: dict, max_len: int = 400) -> str:
    """Kiest de beste samenvattingstekst per brontype.

    - youtube : transcript-fragment heeft voorkeur boven URL-rijke beschrijving
    - podcast : gefilterde show notes
    - web     : eerste zinvolle tekst uit de beschrijving
    """
    source_type = item.get("source_type", "web")
    if source_type == "youtube":
        snippet = item.get("transcript_snippet", "")
        if not snippet:
            snippet = extract_snippet(item.get("description", ""), max_len)
        return snippet[:max_len]
    elif source_type == "podcast":
        return extract_snippet(item.get("description", ""), max_len=max(max_len, 500))
    else:
        return extract_snippet(item.get("description", ""), max_len=max_len)


def detect_source_type(feed_url: str, entry: dict) -> str:
    """Detecteert het brontype op basis van feed-URL en item-enclosures."""
    if "youtube.com/feeds/videos.xml" in feed_url:
        return "youtube"
    enclosures = entry.get("enclosures", [])
    if any(e.get("type", "").startswith("audio/") for e in enclosures):
        return "podcast"
    return "web"


# Einde van het dagelijkse 404-venster op het YouTube-RSS-endpoint, in lokale tijd.
# Gemeten op 12 sep 2026 vanaf drie hosts — waarvan één op een publiek IP buiten ons
# netwerk — liep het venster van 04:03 tot 08:55; buiten het venster faalde geen van de
# 80 controleverzoeken. Het einde valt samen met middernacht Pacific. Zie ADR-0012 in
# ResearchVault-plans en Faalpatroon 34 in ~/bin/RUNBOOK.md.
#
# Deze grens is een aanname over het rooster van een ander en kan dus roesten. Ze
# verraadt zichzelf: loopt het venster ooit dóór tot ná 09:00, dan gaat de dagrun van
# 09:00 feeds melden — hetzelfde signaal waarmee dit verschijnsel oorspronkelijk boven
# kwam. Daarom staat hier geen slimmigheid met tijdzones omheen.
VENSTER_EINDE_UUR = 9


def _is_404(fout):
    """Herkent een HTTP 404 in de fout van een mislukte fetch.

    `FetchResult.error` draagt het exception-object, niet zijn tekst. Daar liep de
    eerste versie van deze regel op stuk. `"404" in fout` wierp géén TypeError bij
    een `urllib.error.HTTPError`: dat object is file-achtig en dus itereerbaar, dus
    de uitdrukking liep stil de HTML-foutpagina af en gaf False — de ochtendbatch
    van 13 sep 2026 zette daardoor alle zestien feeds in de verkeerde emmer. Bij een
    `URLError` (DNS, TLS) wierp dezelfde regel juist wél een TypeError, en die had
    de hele samenvattingsstap meegenomen.

    Vandaar twee expliciete stappen. De statuscode is het gestructureerde signaal en
    staat bij urllib in `.code`; de gerenderde tekst is de terugval voor een fout die
    in iets anders verpakt zit of die een aanroeper als string meegeeft.
    """
    if getattr(fout, "code", None) == 404:
        return True
    return "404" in str(fout or "")


def splits_uitval(failed_feeds, nu):
    """Splitst mislukte feeds in (bekend 404-venster, onverwacht).

    `failed_feeds` is een lijst `(url, status, fout)` — waarbij `fout` het exception-
    object uit `FetchResult.error` is, niet zijn tekst; de volgorde blijft in beide
    uitkomsten behouden. `nu` wordt meegegeven in plaats van hier opgehaald, zodat de
    regel te testen is zonder de klok te manipuleren.

    Een feed telt alleen als bekend venster wanneer alle vier gelden: het is een
    YouTube-feed, de status is `mislukt`, de fouttekst noemt een 404, en de run draait
    vóór VENSTER_EINDE_UUR. Elk van die voorwaarden houdt een echte storing binnen het
    alarm: een time-out is geen weigering, een DNS-fout om 07:00 noemt geen 404, en een
    404 om 14:00 hoort niet bij dit venster.
    """
    bekend = []
    onverwacht = []
    in_venster = nu.hour < VENSTER_EINDE_UUR

    for uitval in failed_feeds:
        url, status, fout = uitval
        if (in_venster
                and status == "mislukt"
                and _is_404(fout)
                and detect_source_type(url, {}) == "youtube"):
            bekend.append(uitval)
        else:
            onverwacht.append(uitval)

    return bekend, onverwacht
