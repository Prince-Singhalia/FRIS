"""Unit tests for CSV validation and tenant scoping."""

import pytest
from app.domain.schemas import validate_orcid, FacultyCreate


class TestCSVValidation:

    def test_faculty_create_valid(self):
        fc = FacultyCreate(
            full_name="Test Researcher",
            reported_institution="Test University",
            department="CS",
            orcid="0000-0002-7481-0810",
            name_variants=["T. Researcher"],
        )
        assert fc.full_name == "Test Researcher"
        assert fc.orcid == "0000-0002-7481-0810"

    def test_faculty_create_no_orcid(self):
        fc = FacultyCreate(full_name="Test Researcher")
        assert fc.orcid is None

    def test_faculty_create_empty_orcid(self):
        fc = FacultyCreate(full_name="Test Researcher", orcid="")
        assert fc.orcid is None

    def test_faculty_create_invalid_orcid(self):
        with pytest.raises(Exception):
            FacultyCreate(full_name="Test", orcid="invalid-orcid")

    def test_faculty_create_name_required(self):
        with pytest.raises(Exception):
            FacultyCreate(full_name="")

    def test_faculty_create_name_variants_list(self):
        fc = FacultyCreate(
            full_name="Test",
            name_variants=["Variant A", "Variant B"],
        )
        assert len(fc.name_variants) == 2

    def test_faculty_create_demo_label(self):
        fc = FacultyCreate(
            full_name="Demo Person",
            is_demo=True,
            demo_label="DEMO — external researcher",
        )
        assert fc.is_demo is True
        assert "DEMO" in fc.demo_label


class TestTenantScoping:
    """Test that domain schemas properly handle tenant-related fields."""

    def test_faculty_create_no_tenant_in_body(self):
        """Tenant should come from auth token, not request body."""
        fc = FacultyCreate(full_name="Test")
        assert not hasattr(fc, "tenant_id")
