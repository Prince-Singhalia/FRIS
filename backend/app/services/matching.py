"""Confidence scoring and author identity resolution service."""

from __future__ import annotations

from app.services.normalization import compute_name_similarity

SCORE_VERSION = "1.0"


def compute_confidence_score(
    orcid_match: bool = False,
    verified_identifier: bool = False,
    institution_match: bool = False,
    name_similarity: float = 0.0,
    coauthor_continuity: bool = False,
    topic_continuity: bool = False,
    chronology_consistent: bool = False,
    has_contradiction: bool = False,
) -> dict:
    """Compute explainable confidence score (0-100).

    Signals and max points:
      - Verified ORCID or linked provider ID: 40
      - Institution/affiliation match: 20
      - Name similarity: 15
      - Co-author continuity: 10
      - Research-topic continuity: 5
      - Chronology/affiliation timeline: 10
      - Maximum: 100

    Decision bands:
      - 85-100 with strong identifier and no contradiction: verified
      - 70-84: probable (review recommended)
      - 50-69: review_required
      - <50: rejected
      - Any hard contradiction forces review_required regardless of score
    """
    points = 0
    positive_evidence: list[dict] = []
    negative_evidence: list[dict] = []

    # Verified ORCID or linked identifier: max 40
    if orcid_match:
        points += 40
        positive_evidence.append(
            {
                "signal": "verified_orcid",
                "points": 40,
                "detail": "ORCID matched faculty profile",
            }
        )
    elif verified_identifier:
        points += 40
        positive_evidence.append(
            {
                "signal": "verified_identifier",
                "points": 40,
                "detail": "Verified provider author ID matched",
            }
        )

    # Institution match: max 20
    if institution_match:
        points += 20
        positive_evidence.append(
            {
                "signal": "institution_match",
                "points": 20,
                "detail": "Institution/affiliation matched",
            }
        )

    # Name similarity: max 15
    name_points = round(name_similarity * 15)
    if name_points > 0:
        points += name_points
        positive_evidence.append(
            {
                "signal": "name_similarity",
                "points": name_points,
                "detail": f"Name similarity score: {name_similarity:.2f}",
            }
        )

    # Co-author continuity: max 10
    if coauthor_continuity:
        points += 10
        positive_evidence.append(
            {
                "signal": "coauthor_continuity",
                "points": 10,
                "detail": "Co-author overlap detected across publications",
            }
        )

    # Topic continuity: max 5
    if topic_continuity:
        points += 5
        positive_evidence.append(
            {
                "signal": "topic_continuity",
                "points": 5,
                "detail": "Research topic overlap with faculty profile",
            }
        )

    # Chronology consistency: max 10
    if chronology_consistent:
        points += 10
        positive_evidence.append(
            {
                "signal": "chronology_consistent",
                "points": 10,
                "detail": "Publication dates consistent with affiliation timeline",
            }
        )

    # Hard contradiction
    if has_contradiction:
        negative_evidence.append(
            {
                "signal": "contradiction",
                "detail": (
                    "Hard contradiction detected (e.g., conflicting ORCID, incompatible "
                    "identifier, or strong affiliation/time contradiction)"
                ),
            }
        )

    # Cap at 100
    score = min(points, 100)

    # Decision band
    if has_contradiction:
        band = "review_required"
        explanation_parts = [f"Score {score}/100"]
        explanation_parts.append(
            "Hard contradiction detected — forced to review regardless of score"
        )
        for ev in positive_evidence:
            explanation_parts.append(f"{ev['signal']}: +{ev['points']}")
        for ev in negative_evidence:
            explanation_parts.append(f"CONTRADICTION: {ev['detail']}")
    elif score >= 85 and (orcid_match or verified_identifier):
        band = "verified"
        explanation_parts = [f"Score {score}/100 — Verified candidate"]
        for ev in positive_evidence:
            explanation_parts.append(f"{ev['signal']}: +{ev['points']}")
    elif score >= 70:
        band = "probable"
        explanation_parts = [f"Score {score}/100 — Probable match, review recommended"]
        for ev in positive_evidence:
            explanation_parts.append(f"{ev['signal']}: +{ev['points']}")
    elif score >= 50:
        band = "review_required"
        explanation_parts = [f"Score {score}/100 — Insufficient evidence for automatic attribution"]
        for ev in positive_evidence:
            explanation_parts.append(f"{ev['signal']}: +{ev['points']}")
    else:
        band = "rejected"
        explanation_parts = [f"Score {score}/100 — Below threshold"]
        for ev in positive_evidence:
            explanation_parts.append(f"{ev['signal']}: +{ev['points']}")

    return {
        "score": score,
        "band": band,
        "positive_evidence": positive_evidence,
        "negative_evidence": negative_evidence,
        "explanation": "; ".join(explanation_parts),
        "has_contradiction": has_contradiction,
        "score_version": SCORE_VERSION,
    }


def evaluate_author_candidate(
    faculty_name: str,
    faculty_orcid: str | None,
    faculty_institution: str | None,
    candidate_name: str | None,
    candidate_orcid: str | None,
    candidate_institution: str | None,
    candidate_provider_id: str | None = None,
    verified_provider_ids: list[dict] | None = None,
) -> dict:
    """Evaluate a candidate author profile against a faculty record.

    Returns score result with evidence.
    """
    # ORCID match
    orcid_match = False
    has_contradiction = False

    if faculty_orcid and candidate_orcid:
        if faculty_orcid.strip().upper() == candidate_orcid.strip().upper():
            orcid_match = True
        else:
            # Different ORCID = hard contradiction
            has_contradiction = True

    # Verified identifier match
    verified_identifier = False
    if verified_provider_ids and candidate_provider_id:
        for vid in verified_provider_ids:
            if vid.get("value") == candidate_provider_id and vid.get("provider"):
                verified_identifier = True
                break

    # Name similarity
    name_sim = 0.0
    if candidate_name:
        name_sim = compute_name_similarity(faculty_name, candidate_name)

    # Institution match (simple substring for MVP)
    institution_match = False
    if faculty_institution and candidate_institution:
        fi = faculty_institution.lower().strip()
        ci = candidate_institution.lower().strip()
        if fi in ci or ci in fi:
            institution_match = True

    return compute_confidence_score(
        orcid_match=orcid_match,
        verified_identifier=verified_identifier,
        institution_match=institution_match,
        name_similarity=name_sim,
        has_contradiction=has_contradiction,
    )
