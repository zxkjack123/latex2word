# Engineering Papers (Fusion & Nuclear)

Scope: Journal and conference papers in fusion engineering and nuclear science & engineering.

1) Structure
- Title
- Authors and affiliations; corresponding author
- Abstract (150–250 words), Keywords (3–6)
- Nomenclature / List of Symbols (optional)
- 1. Introduction (motivation, contribution)
- 2. Methods / Modeling / Experimental Setup
- 3. Results
- 4. Discussion
- 5. Conclusion (and future work)
- Acknowledgments, Funding, Data/Code availability
- References
- Appendices (A, B, …) if needed

2) Numbering & cross-referencing
- Follow ISO 2145: use Arabic numerals; subsections 2.1, 2.1.1; appendices A.1.
- Use automatic cross-references for figures, tables, and equations.

3) Mathematics & equations
- Display equations centered; number right-aligned (1), (2). If by section: (2.1).
- Variables italic; functions upright (sin, exp); vectors/matrices consistently bold or arrow.
- Define symbols at first use; avoid redefining common symbols without notice.

4) Units & measurements
- Use SI (BIPM SI Brochure) and ISO/IEC 80000.
- Non‑SI accepted in nuclear: eV (energy), barn (cross section) with σ, etc. See `../common/units_nuclear.md`.
- Uncertainty reporting per GUM style; align significant figures with uncertainty.

5) Figures & tables
- Figures: clear axis labels with units, consistent tick formatting, captions concise: “Figure 3. Neutron flux map at 1 MeV threshold.”
- Tables: three-line style (top/header/bottom rules), minimal vertical lines; units in headers.
- Use vector graphics for line plots (PDF/SVG/EPS) and ≥300 dpi for bitmaps.

6) References & data/software citation
- Use IEEE numeric style for engineering venues; include DOIs.
- Datasets/software: cite with DOI and version; state license if relevant.
- For Chinese venues, consider GB/T 7714—2015; see `../common/references_styles.md`.

7) Domain conventions (fusion/nuclear)
- Nuclide notation: ²³⁵U, ³H (t). Reactions (n,γ), (n,f), (d,t), with Q in MeV.
- Cross sections in b/mb with σ; flux ϕ (m⁻²·s⁻¹), fluence Φ (m⁻²). Define early.
- Plasma parameters: nₑ (m⁻³), Tₑ (eV or K—state clearly), B (T). Use consistent symbol set.

8) Reproducibility & artifacts
- Provide data availability; link code repositories with tags/releases and CITATION.cff.
- Document numerical settings (meshes, turbulence models, nuclear data libraries).

9) Ethics & compliance
- Acknowledge funding and facility use properly; declare conflicts of interest.
- If biomedical coupling exists, check ICMJE (Vancouver) requirements.

10) Pre-submission checklist
- [ ] SI units; variables italic; functions upright
- [ ] Captions provide what/where/how; figures/tables self-contained
- [ ] Equations numbered and referenced
- [ ] References complete with DOIs; datasets/software cited
- [ ] Nomenclature table included if symbol set is large
- [ ] Uncertainty/significant figures consistent
