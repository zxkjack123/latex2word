# Software Documentation (EN)

Scope: Research software for fusion/nuclear engineering; user docs, API docs, and compliance artifacts.

Document types
- Software Requirements Specification (SRS) — ISO/IEC/IEEE 29148
- Architecture & Design — C4 diagrams, module descriptions
- User Guide — installation, configuration, examples, troubleshooting
- API Reference — auto-generated (Sphinx, Doxygen) with docstrings
- Validation & Verification Report — tests, benchmarks, comparison to references
- Release Notes & Changelog — semantic versioning
- Licensing & Citation — LICENSE, CITATION.cff, AUTHORS

Best practices
- Version all artifacts with releases; archive with DOI (Zenodo) for citations.
- Provide deterministic environments (containers, lock files).
- Include datasets/model inputs with licenses.

Chinese software copyright (简述)
- 准备权属材料、软件说明文档、功能/界面说明、部分源代码节选等。具体页数与格式以中国版权保护中心或主管机关最新要求为准（请以官方指南为准）。

Checklist
- [ ] SRS reflects stakeholder needs and constraints
- [ ] API docs build cleanly from source annotations
- [ ] Examples and test data provided; reproducible runs documented
- [ ] License and citation files present; version tagged
