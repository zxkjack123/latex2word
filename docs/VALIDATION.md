# DOCX Conversion Validation

## Overview

This document describes the automated validation system for checking DOCX conversion quality against scientific writing standards.

## Validation Tool

### Installation

The validation tool is included in the `tex2docx` package. No additional installation is required.

### Usage

#### Command Line

```bash
# Basic validation
python scripts/validate_docx.py output.docx

# Verbose output with detailed issues
python scripts/validate_docx.py output.docx --verbose

# Save report to file
python scripts/validate_docx.py output.docx --output report.txt

# Fail CI pipeline on errors
python scripts/validate_docx.py output.docx --fail-on-error

# Detect SCI compliance issues during conversion
tex2docx convert --input-texfile input.tex --output-docxfile output.docx \
   2>conversion.log
```

The converter now emits warnings when it encounters inline math such as
`480\,\mathrm{ppm}`. These expressions are rewritten to upright plain text,
and the warning suggests the preferred `\SI`/`\num` syntax.
```

#### Python API

```python
from pathlib import Path
from tex2docx.docx_validator import validate_docx

report = validate_docx(Path("output.docx"), verbose=True)

if report.has_errors():
    print("Validation failed!")
    for issue in report.issues:
        print(f"  {issue.severity}: {issue.message}")
```

## Validation Checks

### 1. Superscript Formatting

**Rule**: Superscripts in units and isotope notation must be upright (non-italic).

**Examples**:
- ✅ Correct: `m³` (upright 3)
- ❌ Incorrect: `m³` (italic 3)

**IUPAC Standard**: IUPAC Blue Book 2013, P-81.1–P-81.2

**Implementation**: The validator checks all `<w:r>` elements with `vertAlign="superscript"` and verifies they have `<w:i w:val="0"/>`.

### 2. Subscript Formatting

**Rule**: Subscripts in chemical formulas must be upright (non-italic).

**Examples**:
- ✅ Correct: `CO₂` (upright 2)
- ❌ Incorrect: `CO₂` (italic 2)

**Implementation**: Similar to superscripts, checks `vertAlign="subscript"` elements.

### 3. Units as Plain Text

**Rule**: Units should be rendered as plain text with superscript/subscript formatting, not as OMML math.

**Examples**:
- ✅ Correct: `315 K` as plain text
- ❌ Incorrect: `315 K` as OMML math (`<m:oMath>`)

**Rationale**: OMML math renders letters in italic by default, which is incorrect for units.

**Implementation**: The validator detects OMML math elements that contain unit-like patterns (number + unit symbol).

### 4. Isotope Notation

**Rule**: Isotope mass numbers must be upright superscripts.

**Examples**:
- ✅ Correct: `⁹⁹Mo` (upright 99)
- ❌ Incorrect: `⁹⁹Mo` (italic 99)

**Implementation**: Covered by superscript validation.

### 5. Chemical Formulas

**Rule**: Chemical formula subscripts should be upright, preferably in plain text rather than OMML.

**Examples**:
- ✅ Correct: `CH₄` as plain text
- ⚠️  Warning: `CH₄` subscript in OMML math

**Implementation**: Validator warns when subscripts appear in OMML that look like chemical formula components.

## Known Issues

All previously identified formatting issues for SI units, fragmented
chemical formulas, and labeled decay arrows have been resolved. The
validator currently reports no issues for the regression suite.

Warnings may still appear during conversion if source documents rely on
non-standard unit markup. Update the LaTeX to use `siunitx` commands to
silence these hints.

## Test Cases

### Minimal Test Suite

The file `tests/minimal_unit_test.tex` contains isolated test cases:

```latex
% Test 1: Simple unit with \SI command
Temperature: $\SI{315}{\kelvin}$

% Test 2: Unit fraction with mathrm
Flow rate: $18\,\mathrm{m}^{3}/\mathrm{s}$

% Test 3: Isotope notation
Isotope: $^{99}\mathrm{Mo}$

% Test 4: Chemical formula with subscript
Chemical: HO-CH$_2$-COO$^{-}$

% Test 5: Decay chain with gamma
Decay: $^{99}\mathrm{Mo} \xrightarrow{\gamma} {}^{99m}\mathrm{Tc} + \gamma$
```

### Complex Test Suite

The file `tests/en/mixed_content_complex.tex` contains a comprehensive mix of:
- Inline math
- Chemical notation
- Units
- Isotope notation
- Display equations
- Tables

## Running Tests

### Unit Tests

```bash
pytest tests/test_validation.py -v
```

### Integration Tests

```bash
# Convert and validate minimal test
cd tests
python -m tex2docx convert --input-texfile minimal_unit_test.tex --output-docxfile minimal_unit_test.docx
python ../scripts/validate_docx.py minimal_unit_test.docx --verbose

# Convert and validate complex test
cd en
python -m tex2docx convert --input-texfile mixed_content_complex.tex --output-docxfile mixed_content_complex.docx
python ../../scripts/validate_docx.py mixed_content_complex.docx --verbose
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Validate DOCX Quality
  run: |
    python scripts/validate_docx.py output.docx --fail-on-error
```

## Future Enhancements

1. **Additional Checks**:
   - Figure caption formatting
   - Table caption formatting
   - Reference formatting
   - Cross-reference consistency

2. **Customizable Rules**:
   - Allow users to configure severity levels
   - Support custom validation rules
   - Journal-specific style checks

3. **Auto-Fix Capabilities**:
   - Automatically fix common formatting issues
   - Generate corrected DOCX files

4. **HTML Reports**:
   - Generate visual diff reports
   - Highlight problematic regions in the document

## References

- IUPAC Blue Book 2013: [https://iupac.org/what-we-do/books/bluebook/](https://iupac.org/what-we-do/books/bluebook/)
- IEEE Style Guide: [https://ieeeauthorcenter.ieee.org/](https://ieeeauthorcenter.ieee.org/)
- Office Open XML Standard: [https://www.ecma-international.org/publications-and-standards/standards/ecma-376/](https://www.ecma-international.org/publications-and-standards/standards/ecma-376/)
