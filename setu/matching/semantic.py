"""Free-text semantic matching (step 4 of the cascade).

Family narratives ("wearing a green saree, lost near the blue water tank") and
volunteer notes rarely share exact words but often share meaning. We embed the
free-text of each record and use cosine similarity as an extra, modest signal.

Production: sentence embeddings stored in pgvector with an HNSW index, queried
1-to-few. The CONTRACT is: `embed(text) -> vector`, similarity = cosine, top-k by
ANN. Here `embed()` is a runnable, dependency-free hashed character-n-gram
bag-of-features (clearly a MOCK of a real multilingual embedder) so the demo runs
anywhere; swapping in a real model means replacing `embed()` only.

IMPORTANT: physical_description is QUARANTINED out of this signal by default —
the data shows it is unreliable. Only intentional free_text context is embedded.
The semantic contribution to the score is capped low (see cascade.py).
"""

from __future__ import annotations

import hashlib
import math
import re

DIM = 256  # mock embedding dimensionality


def _tokens(text: str) -> list[str]:
    text = text.lower()
    words = re.findall(r"[a-zऀ-ॿ]+", text)
    grams = []
    for w in words:
        grams.append(w)
        for i in range(len(w) - 2):  # char trigrams for fuzzy overlap
            grams.append(w[i:i + 3])
    return grams


def embed(text: str | None) -> list[float]:
    """MOCK multilingual embedder. Hashed-n-gram bag, L2-normalised.
    Same contract as a real embedder: str -> fixed-dim unit vector."""
    vec = [0.0] * DIM
    if not text:
        return vec
    for tok in _tokens(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def semantic_similarity(text_a: str | None, text_b: str | None) -> float:
    """Cosine similarity in [-1, 1] (typically [0, 1] for these vectors).
    Returns 0.0 if either side has no free text."""
    if not text_a or not text_b:
        return 0.0
    return round(cosine(embed(text_a), embed(text_b)), 4)
