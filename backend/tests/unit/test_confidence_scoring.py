"""Unit tests for confidence scoring — tests production code in app.services.matching."""

import pytest
from app.services.matching import compute_confidence_score


class TestConfidenceScoring:

    def test_verified_orcid_full_match(self):
        result = compute_confidence_score(
            orcid_match=True,
            institution_match=True,
            name_similarity=1.0,
            chronology_consistent=True,
        )
        assert result["score"] == 85
        assert result["band"] == "verified"
        assert not result["has_contradiction"]

    def test_orcid_match_only(self):
        result = compute_confidence_score(orcid_match=True)
        assert result["score"] == 40
        assert result["band"] == "rejected"  # 40 < 50

    def test_orcid_plus_institution(self):
        result = compute_confidence_score(orcid_match=True, institution_match=True)
        assert result["score"] == 60
        assert result["band"] == "review_required"

    def test_name_only_never_verified(self):
        result = compute_confidence_score(name_similarity=1.0)
        assert result["score"] == 15
        assert result["band"] == "rejected"

    def test_high_score_with_contradiction_forces_review(self):
        result = compute_confidence_score(
            orcid_match=True,
            institution_match=True,
            name_similarity=1.0,
            chronology_consistent=True,
            has_contradiction=True,
        )
        assert result["score"] == 85
        assert result["band"] == "review_required"
        assert result["has_contradiction"]

    def test_probable_band(self):
        result = compute_confidence_score(
            orcid_match=True,
            institution_match=True,
            name_similarity=0.8,
        )
        # 40 + 20 + 12 = 72
        assert result["score"] == 72
        assert result["band"] == "probable"

    def test_all_signals_max(self):
        result = compute_confidence_score(
            orcid_match=True,
            institution_match=True,
            name_similarity=1.0,
            coauthor_continuity=True,
            topic_continuity=True,
            chronology_consistent=True,
        )
        # 40+20+15+10+5+10 = 100
        assert result["score"] == 100
        assert result["band"] == "verified"

    def test_zero_score(self):
        result = compute_confidence_score()
        assert result["score"] == 0
        assert result["band"] == "rejected"

    def test_evidence_array_populated(self):
        result = compute_confidence_score(
            orcid_match=True,
            institution_match=True,
        )
        assert len(result["positive_evidence"]) == 2
        signals = [e["signal"] for e in result["positive_evidence"]]
        assert "verified_orcid" in signals
        assert "institution_match" in signals

    def test_score_version_present(self):
        result = compute_confidence_score()
        assert result["score_version"] == "1.0"

    def test_verified_requires_strong_identifier(self):
        """High score without ORCID/identifier should not be 'verified'."""
        result = compute_confidence_score(
            institution_match=True,
            name_similarity=1.0,
            coauthor_continuity=True,
            topic_continuity=True,
            chronology_consistent=True,
        )
        # 0+20+15+10+5+10 = 60
        assert result["band"] == "review_required"
