# Units and Symbols for Fusion and Nuclear Engineering

Audience: English and Chinese technical writers in fusion engineering and nuclear science & engineering. Applies to papers, reports, patents, and software documentation where measurements, formulas, and figures appear.

Authoritative references
- BIPM: The International System of Units (SI Brochure, 9th ed., v3.01, 2025)
- ISO/IEC 80000 series (Quantities and units) – general and domain parts
- NIST SP 811: Guide for the Use of the International System of Units (SI)
- IUPAC Gold Book; IUPAC Green/Red/Blue Books (terminology and chemistry)

Key rules (must-do)
- Use SI as the primary system. Unit symbols are upright roman (m, s, A, K, mol, cd, kg).
- Physical quantities in algebraic expressions use italic letters (v, T, σ), function names upright (sin, exp).
- Single space (nonbreaking if possible) between value and unit: 25 °C, 10 kPa, 3.0 m·s⁻¹.
- Avoid chain slashes; prefer negative powers or centered dot: J·kg⁻¹·K⁻¹, not J/kg/K.
- Use a consistent decimal point (.) and avoid thousands separators in scientific text or use thin space: 12 345.
- Use SI prefixes correctly (k, M, G, m, µ, n, p); one prefix per unit (e.g., µm, not m×10⁻⁶).

Nuclear- and fusion-specific conventions
- Energy: eV, keV, MeV, GeV are non‑SI but accepted with SI; 1 eV = 1.602 176 634×10⁻¹⁹ J. Write “5.0 MeV” (no italic, M uppercase).
- Activity: becquerel, Bq (s⁻¹). Curie (Ci) is non‑SI; prefer Bq.
- Dose: gray, Gy (J·kg⁻¹); equivalent/effective dose: sievert, Sv. Exposure rate and dose rate use s⁻¹ where applicable.
- Cross section: symbol σ (italic) with unit barn, b (non‑SI accepted); submultiples mb, µb. Example: σ = 550 mb.
- Fluence Φ (m⁻²), flux density ϕ (m⁻²·s⁻¹). Define symbol and units at first use.
- Temperature in kelvin (K) for physics; °C acceptable for engineering context with conversion clarity.
- Magnetic field: B in tesla (T), H in A·m⁻¹. Plasma parameters: nₑ (m⁻³), Tₑ (eV or K, specify); β dimensionless.

Nuclide and reaction notation
- Nuclides: left superscript for mass number; left subscript for atomic number if needed: ²³⁵U or \(^{235}\)U; proton p, deuteron d, triton t, alpha α.
- Ions/charges: SO₄²⁻, UO₂²⁺ with superscripts.
- Reactions: (n,γ), (n,f), (d,t); use Unicode arrows if plain text (→, ⇌). Q‑values in MeV: Q = 2.45 MeV.
- Chemical species upright roman letters; element symbols correct case.

Uncertainty and significant figures
- Prefer ISO GUM style: x = 1.234 ± 0.005 m or x = 1.234(5) m; ensure unit applies to both value and uncertainty.
- Report significant figures consistent with uncertainty. Do not over‑report derived quantities.

Formatting details
- Unit symbols are never pluralized: 5 kg (not 5 kgs).
- No period after unit symbols unless at sentence end.
- Degree, minute, second for angles: 30° 15′ 10″; use space between value and symbol groups.
- Percent: use % with no space in most journals or thin space if required by style (check target venue).

Tables and figures
- Place units in column headers or figure axis labels; avoid mixing units inside cells.
- Axis labels with quantity and unit in parentheses or commas, per venue: “Current (A)” or “Current, A”. Be consistent.

Quick checklist
- [ ] Variables italic; functions/constants/unit symbols upright
- [ ] Value–unit spacing and prefix usage correct
- [ ] Non‑SI nuclear units (eV, b) used appropriately with SI as primary
- [ ] Nuclide, ion, reaction notation correct
- [ ] Uncertainty and significant figures consistent
- [ ] Axis/headers include units; table units not mixed into data cells

References
- SI Brochure (BIPM): https://www.bipm.org/en/publications/si-brochure
- NIST SP 811: https://www.nist.gov/publications/guide-use-international-system-units-si
- ISO/IEC 80000 (overview): https://www.iso.org/standard/76921.html
- IUPAC Gold Book: https://goldbook.iupac.org/
