"""Deduplication service — DOI-first dedup with conservative no-DOI matching."""

from __future__ import annotations

from app.services.normalization import normalize_doi, normalize_title


def should_merge_by_doi(doi_a: str | None, doi_b: str | None) -> bool:
    """Check if two records should merge based on DOI.

    Same normalized DOI = same work per the spec.
    """
    if not doi_a or not doi_b:
        return False
    norm_a = normalize_doi(doi_a)
    norm_b = normalize_doi(doi_b)
    if norm_a is None or norm_b is None:
        return False
    return norm_a == norm_b


def should_consider_no_doi_merge(
    title_a: str,
    title_b: str,
    year_a: int | None,
    year_b: int | None,
    similarity_threshold: float = 0.96,
) -> str:
    """Check if two no-DOI records might be duplicates.

    Returns: 'merge', 'review', or 'no_match'

    Provisional threshold: 0.96 for auto-merge.
    0.90-0.96 -> review (manual).
    Below 0.90 -> no match.
    Year must be compatible (within 1 year for online-first vs print).
    """
    from rapidfuzz import fuzz

    norm_a = normalize_title(title_a)
    norm_b = normalize_title(title_b)

    if not norm_a or not norm_b:
        return "no_match"

    similarity = fuzz.ratio(norm_a, norm_b) / 100.0

    if similarity < 0.80:
        return "no_match"

    # Year check
    year_compatible = True
    if year_a is not None and year_b is not None:
        year_compatible = abs(year_a - year_b) <= 1

    if not year_compatible:
        return "no_match"

    if similarity >= similarity_threshold:
        return "merge"
    elif similarity >= 0.90:
        return "review"
    else:
        return "no_match"
