"""DOCX content validator for scientific document quality checking.

This module provides automated validation of DOCX conversion quality
according to scientific writing standards:
- Superscripts and subscripts in units/isotopes should be upright (non-italic)
- Chemical formulas should use proper subscript formatting
- Units should be in plain text, not OMML math
- Isotope notations should be upright
"""

import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a single validation issue found in DOCX."""

    category: str  # 'superscript', 'subscript', 'unit', 'isotope', 'chemical'
    severity: str  # 'error', 'warning', 'info'
    message: str
    context: str = ""  # Surrounding text for context
    xml_snippet: str = ""  # Problematic XML snippet


@dataclass
class ValidationReport:
    """Validation report containing all found issues."""

    issues: List[ValidationIssue] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add an issue to the report."""
        self.issues.append(issue)
        # Update stats.
        if issue.category not in self.stats:
            self.stats[issue.category] = 0
        self.stats[issue.category] += 1

    def has_errors(self) -> bool:
        """Check if report contains any errors."""
        return any(issue.severity == "error" for issue in self.issues)

    def summary(self) -> str:
        """Generate a summary of the validation report."""
        total = len(self.issues)
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")

        lines = [
            f"Validation Summary: {total} issues found",
            f"  Errors: {errors}",
            f"  Warnings: {warnings}",
            f"  Info: {total - errors - warnings}",
            "",
            "Issues by category:",
        ]

        for category, count in sorted(self.stats.items()):
            lines.append(f"  {category}: {count}")

        return "\n".join(lines)


class DocxValidator:
    """Validator for DOCX scientific document quality."""

    # XML namespaces used in DOCX files.
    NAMESPACES = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    }

    def __init__(self, docx_path: Path):
        """Initialize validator with DOCX file path.

        Args:
            docx_path: Path to the DOCX file to validate.
        """
        self.docx_path = Path(docx_path)
        self.report = ValidationReport()
        self._document_xml: Optional[ET.Element] = None

    def validate(self) -> ValidationReport:
        """Run all validation checks and return report.

        Returns:
            ValidationReport containing all found issues.
        """
        logger.info(f"Starting validation of {self.docx_path}")

        try:
            # Load document.xml.
            self._load_document_xml()

            # Run validation checks.
            self._check_superscripts()
            self._check_subscripts()
            self._check_units_in_math()
            self._check_isotope_notation()
            self._check_chemical_formulas()

            logger.info(
                f"Validation complete: {len(self.report.issues)} issues found"
            )

        except Exception as e:
            logger.error(f"Validation failed: {e}", exc_info=True)
            self.report.add_issue(
                ValidationIssue(
                    category="system",
                    severity="error",
                    message=f"Validation failed: {str(e)}",
                )
            )

        return self.report

    def _load_document_xml(self) -> None:
        """Load and parse document.xml from DOCX file."""
        try:
            with zipfile.ZipFile(self.docx_path, "r") as docx:
                with docx.open("word/document.xml") as f:
                    self._document_xml = ET.parse(f).getroot()
        except Exception as e:
            raise RuntimeError(f"Failed to load document.xml: {e}") from e

    def _check_superscripts(self) -> None:
        """Check that superscripts in units/isotopes are upright."""
        if self._document_xml is None:
            return

        # Find all runs with superscript formatting.
        for run in self._document_xml.findall(".//w:r", self.NAMESPACES):
            rpr = run.find("w:rPr", self.NAMESPACES)
            if rpr is None:
                continue

            vert_align = rpr.find("w:vertAlign", self.NAMESPACES)
            if vert_align is None or vert_align.get(
                f"{{{self.NAMESPACES['w']}}}val"
            ) != "superscript":
                continue

            # Check if italic formatting is explicitly set to false.
            italic = rpr.find("w:i", self.NAMESPACES)
            text_elem = run.find("w:t", self.NAMESPACES)
            if text_elem is None:
                continue

            text = text_elem.text or ""

            # Check if this looks like a unit exponent or isotope mass.
            if re.match(r'^[\d\-\+]+$', text):
                if italic is None or italic.get(
                    f"{{{self.NAMESPACES['w']}}}val"
                ) != "0":
                    context = self._get_text_context(run)
                    self.report.add_issue(
                        ValidationIssue(
                            category="superscript",
                            severity="error",
                            message=(
                                f"Superscript '{text}' should be "
                                f"explicitly non-italic"
                            ),
                            context=context,
                            xml_snippet=ET.tostring(
                                run, encoding="unicode"
                            )[:200],
                        )
                    )

    def _check_subscripts(self) -> None:
        """Check that subscripts in chemical formulas are upright."""
        if self._document_xml is None:
            return

        for run in self._document_xml.findall(".//w:r", self.NAMESPACES):
            rpr = run.find("w:rPr", self.NAMESPACES)
            if rpr is None:
                continue

            vert_align = rpr.find("w:vertAlign", self.NAMESPACES)
            if vert_align is None or vert_align.get(
                f"{{{self.NAMESPACES['w']}}}val"
            ) != "subscript":
                continue

            italic = rpr.find("w:i", self.NAMESPACES)
            text_elem = run.find("w:t", self.NAMESPACES)
            if text_elem is None:
                continue

            text = text_elem.text or ""

            # Check if this looks like a chemical formula subscript.
            if re.match(r'^\d+$', text):
                if italic is None or italic.get(
                    f"{{{self.NAMESPACES['w']}}}val"
                ) != "0":
                    context = self._get_text_context(run)
                    self.report.add_issue(
                        ValidationIssue(
                            category="subscript",
                            severity="error",
                            message=(
                                f"Subscript '{text}' should be "
                                f"explicitly non-italic"
                            ),
                            context=context,
                            xml_snippet=ET.tostring(
                                run, encoding="unicode"
                            )[:200],
                        )
                    )

    def _check_units_in_math(self) -> None:
        """Check that units are not rendered as OMML math."""
        if self._document_xml is None:
            return

        # Find all OMML math elements.
        for omath in self._document_xml.findall(".//m:oMath", self.NAMESPACES):
            text_parts = []
            for text_elem in omath.findall(".//m:t", self.NAMESPACES):
                if text_elem.text:
                    text_parts.append(text_elem.text)

            combined_text = "".join(text_parts)

            # Check if this looks like a unit (number + unit symbol).
            # Common patterns: "315 K", "1.8 mol/(m² s)", "2.4×10⁻⁹ m²/s"
            if self._looks_like_unit(combined_text):
                context = self._get_text_context(omath, before=50, after=50)
                self.report.add_issue(
                    ValidationIssue(
                        category="unit",
                        severity="error",
                        message=(
                            f"Unit '{combined_text.strip()}' should be "
                            f"plain text, not OMML math"
                        ),
                        context=context,
                        xml_snippet=ET.tostring(
                            omath, encoding="unicode"
                        )[:300],
                    )
                )

    def _check_isotope_notation(self) -> None:
        """Check isotope notation formatting (e.g., ⁹⁹Mo)."""
        # This is partially covered by superscript check.
        # Additional checks can be added here for specific patterns.
        pass

    def _check_chemical_formulas(self) -> None:
        """Check chemical formula formatting."""
        if self._document_xml is None:
            return

        # Look for chemical formula patterns in OMML math that should be text.
        for omath in self._document_xml.findall(".//m:oMath", self.NAMESPACES):
            text_parts = []
            for text_elem in omath.findall(".//m:t", self.NAMESPACES):
                if text_elem.text:
                    text_parts.append(text_elem.text)

            combined_text = "".join(text_parts)

            # Check for simple subscript patterns like "2" in "CH₂".
            # If OMML contains just a single digit subscript, it's likely
            # a chemical formula component.
            if re.match(r'^\s*\d+\s*$', combined_text):
                # Need to check if this is part of a chemical formula.
                context = self._get_text_context(omath, before=20, after=20)
                if self._context_suggests_chemical(context):
                    self.report.add_issue(
                        ValidationIssue(
                            category="chemical",
                            severity="warning",
                            message=(
                                f"Subscript '{combined_text.strip()}' "
                                f"in OMML may be part of chemical formula"
                            ),
                            context=context,
                            xml_snippet=ET.tostring(
                                omath, encoding="unicode"
                            )[:200],
                        )
                    )

    def _looks_like_unit(self, text: str) -> bool:
        """Check if text looks like a unit expression.

        Args:
            text: Text to check.

        Returns:
            True if text appears to be a unit.
        """
        # Remove whitespace for analysis.
        clean = text.replace(" ", "")

        # Pattern: number + unit symbol.
        # Examples: "315K", "1.8mol", "2.4×10-9m²/s"
        if re.match(r'^\d+(\.\d+)?[a-zA-Z]', clean):
            return True

        # Pattern: just unit symbols (K, mol, m, s, etc.).
        # Common SI units and their combinations.
        unit_pattern = r'^[KkJjWwNnPpAaVvΩΩμµ°℃℉]+(/[a-zA-Z]+)?$'
        if re.match(unit_pattern, clean):
            return True

        # Pattern: number followed by unit abbreviation.
        if re.search(r'\d+\s*[A-Z][a-z]?(\s|$)', text):
            # Could be "315 K" or similar.
            return True

        return False

    def _context_suggests_chemical(self, context: str) -> bool:
        """Check if context suggests chemical formula.

        Args:
            context: Surrounding text context.

        Returns:
            True if context suggests chemical formula.
        """
        # Look for chemical element symbols before/after.
        chemical_elements = [
            "H",
            "C",
            "N",
            "O",
            "S",
            "P",
            "Cl",
            "Br",
            "F",
            "I",
            "Na",
            "K",
            "Ca",
            "Mg",
            "Fe",
            "Cu",
            "Zn",
        ]

        for element in chemical_elements:
            if element in context:
                return True

        # Look for common chemical formula patterns.
        if re.search(r'[A-Z][a-z]?\d', context):
            return True

        return False

    def _get_text_context(
        self, element: ET.Element, before: int = 30, after: int = 30
    ) -> str:
        """Get text context around an XML element.

        Args:
            element: XML element to get context for.
            before: Number of characters before element.
            after: Number of characters after element.

        Returns:
            Context string showing text before and after element.
        """
        # Find parent paragraph.
        para = element
        while para is not None and para.tag != f"{{{self.NAMESPACES['w']}}}p":
            para = self._find_parent(para)

        if para is None:
            return ""

        # Extract all text from paragraph.
        all_text = []
        for text_elem in para.findall(".//w:t", self.NAMESPACES):
            if text_elem.text:
                all_text.append(text_elem.text)
        for text_elem in para.findall(".//m:t", self.NAMESPACES):
            if text_elem.text:
                all_text.append(text_elem.text)

        full_text = "".join(all_text)

        # For simplicity, return the full paragraph text.
        # More sophisticated approach would locate exact position.
        max_len = before + after
        if len(full_text) > max_len:
            return full_text[:max_len] + "..."
        return full_text

    def _find_parent(self, element: ET.Element) -> Optional[ET.Element]:
        """Find parent of an element in the tree.

        Note: ElementTree doesn't maintain parent references,
        so this is a simplified approach.

        Args:
            element: Element to find parent of.

        Returns:
            Parent element or None.
        """
        if self._document_xml is None:
            return None

        for parent in self._document_xml.iter():
            if element in list(parent):
                return parent
        return None


def validate_docx(
    docx_path: Path, verbose: bool = False
) -> ValidationReport:
    """Convenience function to validate a DOCX file.

    Args:
        docx_path: Path to DOCX file.
        verbose: If True, print detailed issues.

    Returns:
        ValidationReport with findings.
    """
    validator = DocxValidator(docx_path)
    report = validator.validate()

    if verbose:
        print(report.summary())
        print("\nDetailed issues:")
        for idx, issue in enumerate(report.issues, 1):
            print(f"\n{idx}. [{issue.severity.upper()}] {issue.category}")
            print(f"   {issue.message}")
            if issue.context:
                print(f"   Context: {issue.context}")

    return report
