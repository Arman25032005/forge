"""Deterministic, dependency-free text embeddings.

This is a hashed bag-of-words vectorizer (the "hashing trick"), not a
learned semantic embedding model. It gives words consistent positions in a
fixed-size vector without needing a vocabulary, a model download, or
network access, and it is genuinely good enough to rank "does this chunk
share vocabulary with this query" — but it has no notion of synonyms or
meaning (e.g. "cheap" and "inexpensive" get no similarity boost from
sharing a meaning). Swapping in a real embedding model (a local
sentence-transformer, or an API-based one) is a drop-in change: everything
downstream only depends on `embed()` returning a fixed-length unit vector.
"""

import hashlib
import math
import re

DIMENSIONS = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def embed(text: str, dimensions: int = DIMENSIONS) -> list[float]:
    """Return an L2-normalized hashed bag-of-words vector for `text`."""
    vector = [0.0] * dimensions
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return vector
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vectors must have the same dimensionality")
    return sum(x * y for x, y in zip(a, b, strict=True))
