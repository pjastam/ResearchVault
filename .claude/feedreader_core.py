"""
feedreader_core.py — Gedeelde rekenkern voor de feedreader
===========================================================
Bevat puur rekenkundige hulpfuncties zonder I/O of feedparser-afhankelijkheden,
zodat ze herbruikbaar zijn vanuit feedreader-score.py, feedreader-learn.py en
toekomstige scripts.
"""

import re

import numpy as np

THRESHOLD_GREEN  = 50
THRESHOLD_YELLOW = 40
THRESHOLD_STAR   = 70  # items met score ≥ dit worden auto-gestefd in FreshRSS/NNW

PRIOR_RELEVANCE = 0.70  # a priori kans dat een item uit de geselecteerde feeds relevant is

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
