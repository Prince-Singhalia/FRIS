"""Normalization utilities for DOI, titles, and author names."""

from __future__ import annotations

import re
import unicodedata


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI for comparison: strip prefixes, lowercase, trim.

    Returns None for invalid DOIs.
    """
    if not doi:
        return None
    cleaned = doi.strip()
    # Remove common URL prefixes
    for prefix in [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
        "DOI:",
    ]:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :]
            break
    cleaned = cleaned.strip().lower()
    # Basic validity: must start with 10.
    if not cleaned.startswith("10."):
        return None
    return cleaned


def normalize_title(title: str | None) -> str | None:
    """Normalize a title for comparison.

    Unicode NFC normalize, lowercase, strip punctuation, collapse whitespace.
    Returns the display-safe title unchanged; use this for comparison only.
    """
    if not title:
        return None
    # Unicode NFC normalization
    normalized = unicodedata.normalize("NFC", title)
    # Lowercase
    normalized = normalized.lower()
    # Remove punctuation except hyphens within words
    normalized = re.sub(r"[^\w\s-]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized if normalized else None


def tokenize_author_name(name: str) -> list[str]:
    """Create normalized tokens from an author name for matching.

    Preserves original; this returns comparison tokens only.
    """
    if not name:
        return []
    normalized = unicodedata.normalize("NFC", name)
    # Remove punctuation
    normalized = re.sub(r"[^\w\s-]", "", normalized)
    tokens = normalized.lower().split()
    return [t for t in tokens if len(t) > 0]


def compute_name_similarity(name_a: str, name_b: str) -> float:
    """Compute similarity between two names using RapidFuzz.

    Returns a 0.0–1.0 score.
    """
    from rapidfuzz import fuzz

    if not name_a or not name_b:
        return 0.0

    # Normalize both names for comparison
    tokens_a = tokenize_author_name(name_a)
    tokens_b = tokenize_author_name(name_b)

    if not tokens_a or not tokens_b:
        return 0.0

    norm_a = " ".join(tokens_a)
    norm_b = " ".join(tokens_b)

    # Use token_sort_ratio for name reordering robustness
    return fuzz.token_sort_ratio(norm_a, norm_b) / 100.0
