"""Tests for DOCX content quality validation."""

from pathlib import Path

import pytest

from tex2docx import LatexToWordConverter
from tex2docx.docx_validator import (
    DocxValidator,
    ValidationIssue,
    validate_docx,
)


TESTS_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_ROOT.parent


@pytest.fixture(scope="module")
def convert_tex(tmp_path_factory):
    """Convert a LaTeX file to DOCX and return the generated path."""

    def _convert(relative_path: Path) -> Path:
        tex_path = PROJECT_ROOT / relative_path
        output_dir = tmp_path_factory.mktemp("docx")
        output_path = output_dir / f"{tex_path.stem}.docx"
        converter = LatexToWordConverter(
            input_texfile=tex_path,
            output_docxfile=output_path,
            debug=False,
        )
        converter.convert()
        return output_path

    return _convert


class TestDocxValidator:
    """Test DOCX content validation functionality."""

    def test_validator_initialization(self, tmp_path):
        """Test validator can be initialized with a path."""
        docx_path = tmp_path / "test.docx"
        docx_path.touch()
        
        validator = DocxValidator(docx_path)
        assert validator.docx_path == docx_path
        assert validator.report is not None

    def test_validation_issue_creation(self):
        """Test creating validation issues."""
        issue = ValidationIssue(
            category="superscript",
            severity="error",
            message="Test message",
            context="Test context",
        )
        
        assert issue.category == "superscript"
        assert issue.severity == "error"
        assert issue.message == "Test message"
        assert issue.context == "Test context"

    def test_validation_report_add_issue(self):
        """Test adding issues to report."""
        from tex2docx.docx_validator import ValidationReport
        
        report = ValidationReport()
        assert len(report.issues) == 0
        
        issue = ValidationIssue(
            category="unit",
            severity="error",
            message="Test",
        )
        report.add_issue(issue)
        
        assert len(report.issues) == 1
        assert "unit" in report.stats
        assert report.stats["unit"] == 1

    def test_validation_report_has_errors(self):
        """Test detecting errors in report."""
        from tex2docx.docx_validator import ValidationReport
        
        report = ValidationReport()
        assert not report.has_errors()
        
        report.add_issue(
            ValidationIssue(
                category="test",
                severity="warning",
                message="Test",
            )
        )
        assert not report.has_errors()
        
        report.add_issue(
            ValidationIssue(
                category="test",
                severity="error",
                message="Test",
            )
        )
        assert report.has_errors()

    def test_validation_report_summary(self):
        """Test generating report summary."""
        from tex2docx.docx_validator import ValidationReport
        
        report = ValidationReport()
        report.add_issue(
            ValidationIssue(
                category="superscript",
                severity="error",
                message="Test 1",
            )
        )
        report.add_issue(
            ValidationIssue(
                category="unit",
                severity="warning",
                message="Test 2",
            )
        )
        
        summary = report.summary()
        assert "2 issues found" in summary
        assert "Errors: 1" in summary
        assert "Warnings: 1" in summary
        assert "superscript: 1" in summary
        assert "unit: 1" in summary


class TestMinimalConversionCases:
    """Test conversion quality for minimal test cases."""

    @pytest.fixture(scope="module")
    def minimal_test_docx(self, convert_tex):
        """Generate DOCX for the minimal test suite."""

        return convert_tex(Path("tests/minimal_unit_test.tex"))

    def test_minimal_test_file_exists(self, minimal_test_docx):
        """Verify minimal test file exists."""
        assert minimal_test_docx.exists(), (
            f"Minimal test file not found: {minimal_test_docx}"
        )

    def test_validate_minimal_test(self, minimal_test_docx):
        """Run validation on minimal test cases."""
        if not minimal_test_docx.exists():
            pytest.skip("Minimal test DOCX not generated")
        
        report = validate_docx(minimal_test_docx, verbose=False)
        assert len(report.issues) == 0

    def test_isotope_notation_upright(self, minimal_test_docx):
        """Test that isotope mass numbers are upright."""
        if not minimal_test_docx.exists():
            pytest.skip("Minimal test DOCX not generated")
        
        report = validate_docx(minimal_test_docx, verbose=False)
        assert len(report.issues) == 0


class TestComplexConversionCases:
    """Test conversion quality for complex mixed content."""

    @pytest.fixture(scope="module")
    def complex_test_docx(self, convert_tex):
        """Generate DOCX for the mixed content document."""

        return convert_tex(Path("tests/en/mixed_content_complex.tex"))

    def test_complex_file_exists(self, complex_test_docx):
        """Verify complex test file exists."""
        if not complex_test_docx.exists():
            pytest.skip(f"Complex test file not found: {complex_test_docx}")

    def test_validate_complex_content(self, complex_test_docx):
        """Run validation on complex mixed content."""
        if not complex_test_docx.exists():
            pytest.skip("Complex test DOCX not generated")
        
        report = validate_docx(complex_test_docx, verbose=False)
        assert len(report.issues) == 0

    def test_no_unit_in_omml(self, complex_test_docx):
        """Test that units are not rendered as OMML math."""
        if not complex_test_docx.exists():
            pytest.skip("Complex test DOCX not generated")
        
        report = validate_docx(complex_test_docx, verbose=False)
        assert len([i for i in report.issues if i.category == "unit"]) == 0
