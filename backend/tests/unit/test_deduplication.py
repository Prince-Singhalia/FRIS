"""Unit tests for DOI-based deduplication — tests production code."""

import pytest
from app.services.deduplication import should_merge_by_doi, should_consider_no_doi_merge


class TestDOIDeduplication:

    def test_same_doi_merges(self):
        assert should_merge_by_doi("10.1234/test", "10.1234/test")

    def test_same_doi_different_case(self):
        assert should_merge_by_doi("10.1234/TEST", "10.1234/test")

    def test_same_doi_with_prefix(self):
        assert should_merge_by_doi("https://doi.org/10.1234/test", "10.1234/test")

    def test_different_doi_no_merge(self):
        assert not should_merge_by_doi("10.1234/test", "10.5678/other")

    def test_none_doi_no_merge(self):
        assert not should_merge_by_doi(None, "10.1234/test")
        assert not should_merge_by_doi("10.1234/test", None)
        assert not should_merge_by_doi(None, None)

    def test_invalid_doi_no_merge(self):
        assert not should_merge_by_doi("not-a-doi", "10.1234/test")


class TestNoDOIDuplicateDetection:

    def test_identical_titles_merge(self):
        result = should_consider_no_doi_merge(
            "ImageNet: A Large-Scale Hierarchical Image Database",
            "ImageNet: A Large-Scale Hierarchical Image Database",
            2009, 2009,
        )
        assert result == "merge"

    def test_slightly_different_titles_review(self):
        result = should_consider_no_doi_merge(
            "Deep Learning for Computer Vision: A Brief Review",
            "Deep Learning for Computer Vision: A Review",
            2018, 2018,
        )
        assert result in ("merge", "review")

    def test_different_titles_no_match(self):
        result = should_consider_no_doi_merge(
            "ImageNet Classification with Deep CNNs",
            "BERT: Pre-training of Deep Bidirectional Transformers",
            2012, 2018,
        )
        assert result == "no_match"

    def test_incompatible_years_no_match(self):
        result = should_consider_no_doi_merge(
            "ImageNet: A Large-Scale Hierarchical Image Database",
            "ImageNet: A Large-Scale Hierarchical Image Database",
            2009, 2015,
        )
        assert result == "no_match"

    def test_preprint_final_not_auto_merged(self):
        """Preprint/final with slightly different titles should go to review."""
        result = should_consider_no_doi_merge(
            "Deep Learning for Vision (Preprint)",
            "Deep Learning for Vision",
            2020, 2020,
        )
        assert result in ("review", "no_match")
