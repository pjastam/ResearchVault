"""
feedreader_core.py — Gedeelde rekenkern voor de feedreader
===========================================================
Bevat puur rekenkundige hulpfuncties zonder I/O of feedparser-afhankelijkheden,
zodat ze herbruikbaar zijn vanuit feedreader-score.py, feedreader-learn.py en
toekomstige scripts.
"""

import numpy as np

THRESHOLD_GREEN  = 50
THRESHOLD_YELLOW = 40

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


def score_label(score: int) -> str:
    if score >= THRESHOLD_GREEN:
        return "🟢"
    elif score >= THRESHOLD_YELLOW:
        return "🟡"
    return "🔴"


def detect_source_type(feed_url: str, entry: dict) -> str:
    """Detecteert het brontype op basis van feed-URL en item-enclosures."""
    if "youtube.com/feeds/videos.xml" in feed_url:
        return "youtube"
    enclosures = entry.get("enclosures", [])
    if any(e.get("type", "").startswith("audio/") for e in enclosures):
        return "podcast"
    return "web"
