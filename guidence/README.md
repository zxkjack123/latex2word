# Guidance for Fusion/Nuclear Documents

This folder provides ready-to-use writing standards for English and Chinese documents in fusion engineering and nuclear science & engineering.

Contents
- common/
  - units_nuclear.md — SI rules + nuclear-specific units, nuclide and reaction notation, uncertainty
  - references_styles.md — IEEE / ISO 690 / GB/T 7714 reference practices and CSL hints
- en/
  - engineering_papers.md — Structure and style for journal/conference papers
  - technical_reports.md — Structure and QA/QC for technical reports
  - patents.md — Patent specification & claims writing (WIPO/USPTO/EPO/CNIPA context)
  - software_docs.md — Software SRS, API docs, V&V, licensing & citation
- zh/
  - 论文规范.md — 中文论文规范（结构、编号、单位、图表、参考文献）
  - 报告规范.md — 技术/研究报告规范
  - 专利规范.md — 专利撰写结构与要点（CN/EN 对照）
  - 软件著作规范.md — 软件文档与登记要点
- checklists/
  - writer_checklist_en.md — Quick checklist (EN)
  - writer_checklist_zh.md — 快速检查清单（ZH）

How to use
- Pick your output language and document type; follow the corresponding guide.
- Enforce SI and reference styles via your LaTeX→DOCX pipeline; see common guides for units and references.
- Include the checklist in internal reviews and CI to prevent regressions.

Authoritative sources
- SI Brochure (BIPM), ISO/IEC 80000, NIST SP 811
- ISO 2145 (numbering), ISO 690 (references)
- IEEE Editorial Style Manual, AMS Style Guide, IUPAC Gold Book
- GB 3100/3101/3102.x, GB/T 7714—2015, GB/T 15835—2011
