"""Unit tests for DOI normalization and title normalization — tests production code."""

import pytest

from app.services.normalization import normalize_doi, normalize_title


class TestDOINormalization:

    def test_basic_doi(self):
        assert normalize_doi("10.1234/test.5678") == "10.1234/test.5678"

    def test_doi_with_https_prefix(self):
        assert normalize_doi("https://doi.org/10.1234/test") == "10.1234/test"

    def test_doi_with_http_prefix(self):
        assert normalize_doi("http://doi.org/10.1234/test") == "10.1234/test"

    def test_doi_with_dx_prefix(self):
        assert normalize_doi("https://dx.doi.org/10.1234/test") == "10.1234/test"

    def test_doi_with_text_prefix(self):
        assert normalize_doi("doi:10.1234/test") == "10.1234/test"

    def test_doi_uppercase(self):
        assert normalize_doi("10.1234/TEST.5678") == "10.1234/test.5678"

    def test_doi_with_whitespace(self):
        assert normalize_doi("  10.1234/test  ") == "10.1234/test"

    def test_invalid_doi_no_10_prefix(self):
        assert normalize_doi("11.1234/test") is None

    def test_none_doi(self):
        assert normalize_doi(None) is None

    def test_empty_doi(self):
        assert normalize_doi("") is None

    def test_real_doi(self):
        assert normalize_doi("https://doi.org/10.1109/CVPR.2009.5206848") == "10.1109/cvpr.2009.5206848"


class TestTitleNormalization:

    def test_basic_title(self):
        assert normalize_title("ImageNet: A Large-Scale Hierarchical Image Database") == \
            "imagenet a large-scale hierarchical image database"

    def test_unicode_normalization(self):
        assert normalize_title("café") == normalize_title("café")

    def test_whitespace_collapse(self):
        assert normalize_title("Deep   Learning   for   Vision") == "deep learning for vision"

    def test_none_title(self):
        assert normalize_title(None) is None

    def test_empty_title(self):
        assert normalize_title("") is None

    def test_punctuation_removal(self):
        result = normalize_title("What, Where, and How: A Survey")
        assert "," not in result
        assert ":" not in result
