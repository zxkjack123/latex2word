#!/usr/bin/env python3
"""CLI tool for validating DOCX conversion quality.

This script validates DOCX files against scientific writing standards
and generates comprehensive reports.
"""

import argparse
import sys
from pathlib import Path

from tex2docx.docx_validator import validate_docx


def main():
    """Main entry point for validation CLI."""
    parser = argparse.ArgumentParser(
        description="Validate DOCX conversion quality for scientific documents"
    )
    parser.add_argument(
        "docx_file",
        type=Path,
        help="Path to DOCX file to validate",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed issue descriptions",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit with non-zero status if errors found",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save validation report to file",
    )

    args = parser.parse_args()

    if not args.docx_file.exists():
        print(f"Error: File not found: {args.docx_file}", file=sys.stderr)
        return 1

    # Run validation
    report = validate_docx(args.docx_file, verbose=args.verbose)

    # Save report if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report.summary())
            f.write("\n\nDetailed Issues:\n")
            for idx, issue in enumerate(report.issues, 1):
                severity = issue.severity.upper()
                f.write(f"\n{idx}. [{severity}] {issue.category}\n")
                f.write(f"   {issue.message}\n")
                if issue.context:
                    f.write(f"   Context: {issue.context}\n")
        print(f"Report saved to: {args.output}")

    # Exit with appropriate status
    if args.fail_on_error and report.has_errors():
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
