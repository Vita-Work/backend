from __future__ import annotations

import math
from difflib import SequenceMatcher
from urllib.parse import urldefrag, urlsplit, urlunsplit


def canonical_job_url(url: str) -> str:
    """Normalize a job URL for deterministic dedupe checks."""
    url_no_fragment, _ = urldefrag(url.strip())
    parts = urlsplit(url_no_fragment)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def normalize_text(value: str | None) -> str:
    """Normalize human text for fingerprints and lexical matching."""
    if not value:
        return ""
    return " ".join(value.lower().split())


def text_similarity(left: str | None, right: str | None) -> float:
    """Return a lightweight lexical similarity score in [0, 1]."""
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    if not left_normalized or not right_normalized:
        return 0.0

    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    token_union = left_tokens | right_tokens
    token_similarity = len(left_tokens & right_tokens) / len(token_union) if token_union else 0.0
    sequence_similarity = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return max(token_similarity, sequence_similarity)


def locations_compatible(left: str | None, right: str | None) -> bool:
    """Treat missing locations as compatible and preserve remote-friendly matching."""
    left_normalized = normalize_text(left)
    right_normalized = normalize_text(right)
    if not left_normalized or not right_normalized:
        return True
    if "remote" in left_normalized and "remote" in right_normalized:
        return True
    return text_similarity(left_normalized, right_normalized) >= 0.8


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return cosine similarity for two equal-length dense vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(
        left_value * right_value for left_value, right_value in zip(left, right, strict=False)
    )
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)
