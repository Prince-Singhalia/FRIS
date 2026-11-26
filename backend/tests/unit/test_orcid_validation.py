"""Unit tests for ORCID validation, DOI normalization, and confidence scoring."""

import pytest

from app.domain.schemas import validate_orcid


class TestORCIDValidation:
    """ORCID format and checksum validation tests."""

    def test_valid_orcid(self):
        result = validate_orcid("0000-0002-7481-0810")
        assert result == "0000-0002-7481-0810"

    def test_valid_orcid_with_x_checksum(self):
        # 0000-0001-5109-018X has check digit X (checksum=10)
        result = validate_orcid("0000-0001-5109-018X")
        assert result == "0000-0001-5109-018X"

    def test_orcid_with_url_prefix(self):
        result = validate_orcid("https://orcid.org/0000-0002-7481-0810")
        assert result == "0000-0002-7481-0810"

    def test_orcid_with_http_prefix(self):
        result = validate_orcid("http://orcid.org/0000-0002-7481-0810")
        assert result == "0000-0002-7481-0810"

    def test_orcid_lowercase_x(self):
        # Should uppercase X
        result = validate_orcid("0000-0001-5109-018x")
        assert result == "0000-0001-5109-018X"

    def test_invalid_format_too_short(self):
        with pytest.raises(ValueError, match="Invalid ORCID"):
            validate_orcid("0000-0002-7481")

    def test_invalid_format_no_dashes(self):
        with pytest.raises(ValueError, match="Invalid ORCID"):
            validate_orcid("0000000274810810")

    def test_invalid_checksum(self):
        with pytest.raises(ValueError, match="checksum"):
            validate_orcid("0000-0002-7481-0811")  # wrong check digit

    def test_invalid_characters(self):
        with pytest.raises(ValueError, match="Invalid ORCID"):
            validate_orcid("0000-000A-7481-0810")

    def test_empty_string(self):
        with pytest.raises(ValueError):
            validate_orcid("")

    def test_whitespace_trimming(self):
        result = validate_orcid("  0000-0002-7481-0810  ")
        assert result == "0000-0002-7481-0810"
