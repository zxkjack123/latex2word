"""Integration tests for the LatexToWordConverter class.

This module contains end-to-end integration tests that verify the complete
conversion workflow from LaTeX documents to Word documents. These tests
exercise the full functionality of the tex2docx package by running actual
conversions and checking that output files are generated successfully.

Test scenarios:
- Basic English document conversion
- English document with chapters
- English document with includes
- Chinese document conversion

Note: These tests require manual verification of the generated Word documents
to ensure proper formatting, references, and content layout.
"""

import base64
import zipfile
from xml.etree import ElementTree as ET
from textwrap import dedent
import pytest  # Use pytest instead of unittest
from pathlib import Path  # Use pathlib for better path handling
from typing import Dict, Any

from tex2docx import LatexToWordConverter
from tex2docx.exceptions import FileNotFoundError

# Get the directory where the test file is located using pathlib
TEST_DIR: Path = Path(__file__).parent.resolve()
# Get the project root directory (assuming tests is one level down)
PROJECT_ROOT: Path = TEST_DIR.parent

_MINIMAL_PNG: str = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42"
    "mP8Xw8AAn0B9nLtV9kAAAAASUVORK5CYII="
)

_W_NS: str = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_W_STYLE_VAL: str = f"{_W_NS}val"


def _write_dummy_png(path: Path) -> None:
    """Write a minimal 1x1 PNG image to the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(_MINIMAL_PNG))


def _extract_docx_text(docx_path: Path) -> str:
    """Return concatenated textual content from a DOCX document."""
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    texts = [
        node.text
        for node in root.iter(f"{_W_NS}t")
        if node.text
    ]
    return " ".join(texts)


def _extract_docx_captions(docx_path: Path) -> list[str]:
    """Return caption paragraphs extracted from a DOCX document."""
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    captions: list[str] = []

    for paragraph in root.iter(f"{_W_NS}p"):
        style = paragraph.find(f"{_W_NS}pPr/{_W_NS}pStyle")
        texts = [
            node.text
            for node in paragraph.iter(f"{_W_NS}t")
            if node.text
        ]
        if not texts:
            continue

        text = "".join(texts).strip()
        style_val = style.attrib.get(_W_STYLE_VAL) if style is not None else ""

        if style_val and "caption" in style_val.lower():
            captions.append(text)
            continue

        if (
            text.startswith("Figure")
            or text.startswith("Table")
            or text.startswith("图")
            or text.startswith("表")
        ):
            captions.append(text)

    return captions


def _load_document_root(docx_path: Path) -> ET.Element:
    """Return the root element for the DOCX main document part."""

    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    return ET.fromstring(xml_bytes)


def _all_tables_centered(docx_path: Path) -> bool:
    """Return True if all tables in the DOCX are center aligned."""

    root = _load_document_root(docx_path)

    for table in root.iter(f"{_W_NS}tbl"):
        jc = table.find(f"{_W_NS}tblPr/{_W_NS}jc")
        if jc is None:
            return False
        if jc.attrib.get(_W_STYLE_VAL) != "center":
            return False

    return True


def _all_drawing_paragraphs_centered(docx_path: Path) -> bool:
    """Return True if paragraphs hosting drawings are centered."""

    root = _load_document_root(docx_path)

    for paragraph in root.iter(f"{_W_NS}p"):
        if paragraph.find(f".//{_W_NS}drawing") is None:
            continue
        jc = paragraph.find(f"{_W_NS}pPr/{_W_NS}jc")
        if jc is None:
            return False
        if jc.attrib.get(_W_STYLE_VAL) != "center":
            return False

    return True


# Define fixtures for test configurations using pytest.fixture
# This replaces the setUp method from unittest.
@pytest.fixture(scope="module")
def en_config() -> Dict[str, Any]:
    """Provides configuration for the English basic test."""
    return {
        "input_texfile": TEST_DIR / "en/main.tex",
        "output_docxfile": TEST_DIR / "en/main.docx",
        # Assuming reference/csl files are in the project root
        "reference_docfile": PROJECT_ROOT / "my_temp.docx",
        "cslfile": PROJECT_ROOT / "ieee.csl",
        # Assuming bib file is in the tests directory
        "bibfile": TEST_DIR / "ref.bib",
        "debug": True,
    }


@pytest.fixture(scope="module")
def en_chapter_config() -> Dict[str, Any]:
    """Provides configuration for the English chapter test."""
    return {
        "input_texfile": TEST_DIR / "en_chapter/main.tex",
        "output_docxfile": TEST_DIR / "en_chapter/main.docx",
        "reference_docfile": PROJECT_ROOT / "my_temp.docx",
        "cslfile": PROJECT_ROOT / "ieee.csl",
        "bibfile": TEST_DIR / "ref.bib",
        "debug": True,
    }


@pytest.fixture(scope="module")
def en_include_config() -> Dict[str, Any]:
    """Provides configuration for the English include test."""
    return {
        "input_texfile": TEST_DIR / "en_include/main.tex",
        "output_docxfile": TEST_DIR / "en_include/main.docx",
        "cslfile": PROJECT_ROOT / "ieee.csl",
        "bibfile": TEST_DIR / "ref.bib",
        "debug": True,
    }


@pytest.fixture(scope="module")
def zh_config() -> Dict[str, Any]:
    """Provides configuration for the Chinese test."""
    return {
        "input_texfile": TEST_DIR / "zh/main.tex",
        "output_docxfile": TEST_DIR / "zh/main.docx",
        "bibfile": TEST_DIR / "ref.bib",
        "fix_table": True,
        "debug": False,
        "caption_locale": "zh",
    }


# Test functions now accept fixtures as arguments
def test_convert_en(en_config: Dict[str, Any]) -> None:
    """Tests conversion for the basic English document."""
    # Ensure output directory exists, or handle potential errors
    output_path: Path = Path(en_config["output_docxfile"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converter = LatexToWordConverter(**en_config)
    converter.convert()

    # Assert that the output file exists and is not empty.
    assert output_path.exists(), f"Output file not found: {output_path}"
    assert (
        output_path.stat().st_size > 0
    ), f"Output file is empty: {output_path}"

    captions = _extract_docx_captions(output_path)
    assert any(
        cap.startswith("Figure 1") for cap in captions
    ), captions
    assert any(
        cap.startswith("Table 1") for cap in captions
    ), captions

    docx_text = _extract_docx_text(output_path)
    assert "title of the article" in docx_text.lower()
    assert _all_tables_centered(output_path)
    assert _all_drawing_paragraphs_centered(output_path)
    # Remind the user to manually check the generated file.
    print(f"\n[Manual Check] Please verify: {output_path}")


def test_convert_en_chapter(en_chapter_config: Dict[str, Any]) -> None:
    """Tests conversion for the English document with chapters."""
    output_path: Path = Path(en_chapter_config["output_docxfile"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converter = LatexToWordConverter(**en_chapter_config)
    converter.convert()

    # Assert that the output file exists and is not empty.
    assert output_path.exists(), f"Output file not found: {output_path}"
    assert (
        output_path.stat().st_size > 0
    ), f"Output file is empty: {output_path}"

    captions = _extract_docx_captions(output_path)
    assert any(
        cap.startswith("Figure 1") or cap.startswith("Figure 1.")
        for cap in captions
    ), captions
    assert any(
        cap.startswith("Table 1") or cap.startswith("Table 1.")
        for cap in captions
    ), captions

    docx_text = _extract_docx_text(output_path)
    assert "References" in docx_text
    # Remind the user to manually check the generated file.
    print(f"\n[Manual Check] Please verify: {output_path}")


def test_convert_en_include(en_include_config: Dict[str, Any]) -> None:
    """Tests conversion for the English document with includes."""
    output_path: Path = Path(en_include_config["output_docxfile"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converter = LatexToWordConverter(**en_include_config)
    converter.convert()

    # Assert that the output file exists and is not empty.
    assert output_path.exists(), f"Output file not found: {output_path}"
    assert (
        output_path.stat().st_size > 0
    ), f"Output file is empty: {output_path}"

    captions = _extract_docx_captions(output_path)
    assert any(
        cap.startswith("Figure 1") for cap in captions
    ), captions
    assert any(
        cap.startswith("Table 1") for cap in captions
    ), captions

    docx_text = _extract_docx_text(output_path)
    normalized_text = docx_text.replace("\u00a0", " ")
    assert "Figure 1:" in docx_text
    assert "Table 1:" in docx_text
    assert "Fig. 1" in normalized_text
    # Remind the user to manually check the generated file.
    print(f"\n[Manual Check] Please verify: {output_path}")


def test_convert_zh(zh_config: Dict[str, Any]) -> None:
    """Tests conversion for the Chinese document."""
    output_path: Path = Path(zh_config["output_docxfile"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    converter = LatexToWordConverter(**zh_config)
    converter.convert()

    # Assert that the output file exists and is not empty.
    assert output_path.exists(), f"Output file not found: {output_path}"
    assert (
        output_path.stat().st_size > 0
    ), f"Output file is empty: {output_path}"

    captions = _extract_docx_captions(output_path)
    assert any(cap.startswith("图 1") for cap in captions), captions
    assert any(cap.startswith("表 1") for cap in captions), captions

    docx_text = _extract_docx_text(output_path)
    assert "示例全球经济指标" in docx_text
    normalized_text = docx_text.replace("\u00a0", " ")
    normalized_compact = normalized_text.replace(" ", "")
    assert "图1" in normalized_compact
    assert "表1" in normalized_compact
    assert "Figure" not in docx_text
    assert "Table" not in docx_text
    # Remind the user to manually check the generated file.
    print(f"\n[Manual Check] Please verify: {output_path}")


def test_missing_figure_asset(tmp_path: Path) -> None:
    """Ensure conversion fails early when figure assets are missing."""
    project_root = PROJECT_ROOT
    work_dir = tmp_path / "missing_figures"
    figures_dir = work_dir / "figs"
    figures_dir.mkdir(parents=True, exist_ok=True)

    tex_content = r"""
    \documentclass{article}
    \usepackage{graphicx}
    \graphicspath{{./figs/}}
    \begin{document}
    \begin{figure}
        \centering
        \includegraphics{nonexistent-figure}
        \caption{Missing asset example}
        \label{fig:missing}
    \end{figure}
    \end{document}
    """

    input_texfile = work_dir / "main.tex"
    input_texfile.write_text(tex_content, encoding="utf-8")

    output_docxfile = work_dir / "main.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        reference_docfile=project_root / "my_temp.docx",
        cslfile=project_root / "ieee.csl",
        debug=True,
    )

    with pytest.raises(FileNotFoundError, match="Missing graphic assets"):
        converter.convert()

    assert not output_docxfile.exists(), (
        "DOCX should not be created when figure assets are missing"
    )


def test_graphicspath_multiple_directories(tmp_path: Path) -> None:
    r"""Assets resolve when located in later ``\graphicspath`` entries."""
    work_dir = tmp_path / "multi_graphicspath"
    primary_dir = work_dir / "figs_primary"
    secondary_dir = work_dir / "figs_secondary"
    primary_dir.mkdir(parents=True, exist_ok=True)
    secondary_dir.mkdir(parents=True, exist_ok=True)
    _write_dummy_png(secondary_dir / "example.png")

    tex_content = r"""
    \documentclass{article}
    \usepackage{graphicx}
    \graphicspath{{./figs_primary/}{./figs_secondary/}}
    \begin{document}
    \begin{figure}
        \centering
        \includegraphics [width=0.75\linewidth] {example}
        \caption{Multi-path lookup}
    \end{figure}
    \end{document}
    """

    input_texfile = work_dir / "main.tex"
    input_texfile.parent.mkdir(parents=True, exist_ok=True)
    input_texfile.write_text(tex_content, encoding="utf-8")
    output_docxfile = work_dir / "main.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        debug=True,
    )
    converter.convert()

    assert output_docxfile.exists()

    captions = _extract_docx_captions(output_docxfile)
    assert all("Nested asset" not in cap for cap in captions), captions
    assert any(
        cap.startswith("Figure 1") and "Multi" in cap
        for cap in captions
    ), captions


def test_include_respects_local_graphicspath(tmp_path: Path) -> None:
    r"""Assets referenced from included files honor local ``\graphicspath``."""
    work_dir = tmp_path / "include_override"
    include_dir = work_dir / "chapters"
    figs_dir = include_dir / "figs"
    include_dir.mkdir(parents=True, exist_ok=True)
    _write_dummy_png(figs_dir / "nested.png")

    main_content = r"""
    \documentclass{article}
    \usepackage{graphicx}
    \begin{document}
    \include{chapters/chapter1}
    \end{document}
    """

    chapter_content = r"""
    \graphicspath{{./figs/}}
    \begin{figure}
        \centering
        \includegraphics{nested}
        \caption{Nested asset}
    \end{figure}
    """

    input_texfile = work_dir / "main.tex"
    input_texfile.parent.mkdir(parents=True, exist_ok=True)
    input_texfile.write_text(main_content, encoding="utf-8")
    chapter_file = include_dir / "chapter1.tex"
    chapter_file.write_text(chapter_content, encoding="utf-8")
    output_docxfile = work_dir / "main.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        debug=True,
    )
    converter.convert()

    assert output_docxfile.exists()


def test_multiple_citations_render(tmp_path: Path) -> None:
    """References list includes all cited entries."""
    work_dir = tmp_path / "multi_citations"
    work_dir.mkdir(parents=True, exist_ok=True)

    latex_content = dedent(
        r"""
        \documentclass{article}
        \begin{document}
        We cite several works~\cite{ref1,ref2,ref3} in sequence.

        \bibliographystyle{ieeetr}
        \bibliography{refs}
        \end{document}
        """
    )

    input_texfile = work_dir / "main.tex"
    input_texfile.write_text(latex_content, encoding="utf-8")

    bib_content = dedent(
        r"""
        @article{ref1,
          author = {Alpha, Alice},
          title = {Comprehensive Guide to Testing},
          journal = {Quality Journal},
          year = {2020}
        }

        @book{ref2,
          author = {Beta, Bob},
          title = {Advanced Conversion Workflows},
          year = {2021},
          publisher = {Publishing House}
        }

        @inproceedings{ref3,
          author = {Gamma, Gina},
          title = {Edge Cases in Document Pipelines},
          booktitle = {Proceedings of TestingConf},
          year = {2022}
        }
        """
    )

    bibfile = work_dir / "refs.bib"
    bibfile.write_text(bib_content, encoding="utf-8")

    output_docxfile = work_dir / "main.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        reference_docfile=PROJECT_ROOT / "my_temp.docx",
        cslfile=PROJECT_ROOT / "ieee.csl",
        bibfile=bibfile,
        debug=True,
    )
    converter.convert()

    docx_text = _extract_docx_text(output_docxfile)
    assert output_docxfile.exists()
    assert "References" in docx_text
    normalized = docx_text.lower()
    assert "comprehensive guide to testing" in normalized
    assert "advanced conversion workflows" in normalized
    assert "edge cases in document pipelines" in normalized


def test_mixed_content_document(tmp_path: Path) -> None:
    """Mixed inline math stays classified correctly after conversion."""

    input_texfile = TEST_DIR / "en/mixed_content.tex"
    output_docxfile = TEST_DIR / "en/mixed_content.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        debug=False,
    )

    converter.convert()

    try:
        assert output_docxfile.exists()

        with zipfile.ZipFile(output_docxfile) as zf:
            xml_bytes = zf.read("word/document.xml")
        xml_text = xml_bytes.decode("utf-8")

        assert "203" in xml_text and "Pb" in xml_text
        assert "15" in xml_text and "/s" in xml_text

        assert "<m:t>203<" not in xml_text
        assert "<m:t>Pb<" not in xml_text

        assert "<m:oMath" in xml_text
        assert "<m:t>x</m:t>" in xml_text or "<m:t>x_i" in xml_text
    finally:
        if output_docxfile.exists():
            output_docxfile.unlink()


def test_mixed_content_complex_document(tmp_path: Path) -> None:
    """Complex chemical notation converts without spurious math runs."""

    input_texfile = TEST_DIR / "en/mixed_content_complex.tex"
    output_docxfile = tmp_path / "mixed_content_complex.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        debug=False,
    )

    converter.convert()

    actual_output = Path(converter.config.output_docxfile)

    try:
        assert actual_output.exists()

        with zipfile.ZipFile(actual_output) as zf:
            xml_text = zf.read("word/document.xml").decode("utf-8")

        assert "→" in xml_text
        assert "×10" in xml_text
        assert "ns1:t>CH" not in xml_text
        assert "CH" in xml_text
        assert "ns1:t>15" not in xml_text
        assert "COO" in xml_text
    finally:
        if actual_output.exists() and actual_output.is_file():
            actual_output.unlink()


def test_numbered_references_roundtrip(tmp_path: Path) -> None:
    """Figures, tables, and equations keep numbered references in DOCX."""
    work_dir = tmp_path / "numbered_refs"
    assets_dir = work_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    _write_dummy_png(assets_dir / "demo.png")

    latex_content = dedent(
        r"""
        \documentclass{article}
        \usepackage{graphicx}
        \graphicspath{{./assets/}}
        \begin{document}
        See Fig.~\ref{fig:demo}, Table~\ref{tbl:demo}, and Eq.~\ref{eq:demo}.

        \begin{figure}
            \centering
            \includegraphics{demo.png}
            \caption{Demo figure}
            \label{fig:demo}
        \end{figure}

        \begin{table}
            \centering
            \caption{Demo table}
            \label{tbl:demo}
            \begin{tabular}{cc}
            A & B \\
            1 & 2 \\
            \end{tabular}
        \end{table}

        \begin{equation}
            \label{eq:demo}
            a = b
        \end{equation}
        \end{document}
        """
    )

    input_texfile = work_dir / "main.tex"
    input_texfile.write_text(latex_content, encoding="utf-8")
    output_docxfile = work_dir / "main.docx"

    converter = LatexToWordConverter(
        input_texfile=input_texfile,
        output_docxfile=output_docxfile,
        fix_table=False,
        debug=True,
    )
    converter.convert()

    assert output_docxfile.exists()

    docx_text = _extract_docx_text(output_docxfile)

    assert "Figure 1" in docx_text
    assert "Table 1" in docx_text
    assert "Fig.\u00a01" in docx_text
    assert "Table\u00a01" in docx_text
    assert "(1)" in docx_text

# The if __name__ == "__main__": block is removed because pytest handles
# test discovery.
