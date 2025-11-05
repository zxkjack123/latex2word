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


def _write_dummy_png(path: Path) -> None:
    """Write a minimal 1x1 PNG image to the given path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(_MINIMAL_PNG))


def _extract_docx_text(docx_path: Path) -> str:
    """Return concatenated textual content from a DOCX document."""
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    texts = [node.text for node in root.iter(f"{_W_NS}t") if node.text]
    return " ".join(texts)


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
