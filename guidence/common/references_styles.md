# References and Citation Styles for Fusion/Nuclear Documents

This guide aligns reference practices for English and Chinese outputs in fusion engineering and nuclear science.

Authoritative references
- ISO 690:2021 — Bibliographic references and citations
- IEEE Editorial Style Manual — Engineering journals
- ICMJE (Vancouver) — Biomedical/medical physics
- GB/T 7714—2015 — Chinese references

English outputs
- Primary styles: IEEE (numeric) for engineering; AMS for math-heavy; Vancouver (ICMJE) for biomed.
- IEEE in-text: numeric bracketed [1], [2]; place before period unless journal overrides.
- Include DOI when available; include accessed date for URLs.
- Preprints: cite arXiv with identifier; datasets/software: cite with DOI (Zenodo, Figshare) using “dataset”/“software” types.

Chinese outputs
- Use GB/T 7714—2015 numeric style；支持作者—年份体例但工程类多用顺序编码制。
- 文献类型标识：期刊[J]、图书[M]、会议[C]、报告[R]、学位[D]、标准[S]、专利[P]、数据库/数据集[DB/DS]、软件[CP/SW] 等。
- 网络资源给出“获取/访问日期”。

Pandoc / CSL usage
- For English IEEE: use `ieee.csl` (already included in this repo as `tex2docx/ieee.csl`).
- For Chinese GB/T 7714—2015: use a 2015 数字顺序 CSL（建议检索 gbt-7714-2015-numeric.csl）。
- Bib fields: ensure DOI, URL, access date, language, and type are properly set for datasets/software.

Reference list hygiene
- Normalize author names (IEEE initials), title capitalization per style, journal abbreviations as required.
- One consistent style per document; do not mix IEEE and Vancouver.
- Order matches in-text first appearance (numeric styles).

Edge cases
- Standards: include issuing body, standard number, edition, year, title, URL/DOI if any.
- Patents: include country/office, patent number, year, title, inventors, assignee.
- Software: cite release/version, DOI, repository URL, year, maintainers.

Quick checklist
- [ ] Pick one style (IEEE/GB/T 7714/others) and keep it consistent
- [ ] Every reference with DOI has DOI included
- [ ] URLs have access dates (non-DOI web resources)
- [ ] Datasets/software cited with type and version
- [ ] Standards and patents carry official numbers and offices
