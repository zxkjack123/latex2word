"""Unit tests for the tex2docx package.

This module contains unit tests for individual functions and classes
in the tex2docx package. These tests verify that each component works
correctly in isolation and provide good test coverage for the codebase.

Test categories:
- ConversionConfig: Configuration validation and setup
- PatternMatcher: Text pattern matching utilities
- TextProcessor: Text processing and manipulation
- LatexParser: LaTeX document parsing functionality
- Constants: Template and pattern definitions
- Integration: Component interaction testing
- Performance: Performance and scalability testing
"""

import asyncio
import json
import logging
import subprocess
import tempfile
from xml.etree import ElementTree as ET
from textwrap import dedent
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import patch

import pytest

import tex2docx.mcp_server as mcp_server
import tex2docx.subfile as subfile_module

from tex2docx import LatexToWordConverter
from tex2docx.config import ConversionConfig, YamlValue
from tex2docx.exceptions import ConversionError, Tex2DocxError
from tex2docx.constants import PandocOptions, TexPatterns, TexTemplates
from tex2docx.authors import parse_author_metadata
from tex2docx.converter import PandocConverter
from tex2docx.modifier import ContentModifier
from tex2docx.parser import LatexParser
from tex2docx.subfile import SubfileCompiler
from tex2docx.utils import PatternMatcher, TextProcessor


class TestConversionConfig:
    """Test the ConversionConfig class."""
    
    def test_config_initialization(self, tmp_path):
        """Test basic config initialization."""
        input_file = tmp_path / "test.tex"
        output_file = tmp_path / "test.docx"
        input_file.write_text(
            "\\documentclass{article}"
            "\\begin{document}Test\\end{document}"
        )
        
        config = ConversionConfig(
            input_texfile=input_file,
            output_docxfile=output_file,
            debug=True
        )
        
        assert config.input_texfile == input_file.resolve()
        assert config.output_docxfile == output_file.resolve()
        assert config.debug is True
        assert config.fix_table is False
        assert config.output_texfile is not None
        assert config.temp_subtexfile_dir is not None
    
    def test_config_missing_input_file(self, tmp_path):
        """Test config with missing input file."""
        input_file = tmp_path / "nonexistent.tex"
        output_file = tmp_path / "test.docx"
        
        with pytest.raises(
            FileNotFoundError,
            match="Input TeX file not found",
        ):
            ConversionConfig(
                input_texfile=input_file,
                output_docxfile=output_file
            )
    
    def test_config_logger_setup(self, tmp_path):
        """Test logger setup."""
        input_file = tmp_path / "test.tex"
        output_file = tmp_path / "test.docx"
        input_file.write_text(
            "\\documentclass{article}"
            "\\begin{document}Test\\end{document}"
        )
        
        config = ConversionConfig(
            input_texfile=input_file,
            output_docxfile=output_file,
            debug=True
        )
        
        logger = config.setup_logger()
        assert logger.level == logging.DEBUG
        
        config.debug = False
        logger2 = config.setup_logger()
        assert logger2.level == logging.INFO

    def test_metadata_override_generation(self, tmp_path):
        """Metadata overrides include localized captions and authors."""

        input_file = tmp_path / "meta.tex"
        output_file = tmp_path / "meta.docx"
        input_file.write_text(
            "\\documentclass{article}"
            "\\begin{document}x\\end{document}"
        )

        config = ConversionConfig(
            input_texfile=input_file,
            output_docxfile=output_file,
        )

        default_metadata = config.get_metadata_file()
        assert default_metadata == PandocOptions.METADATA_FILE

        config.apply_caption_preferences(locale="zh")
        config.set_author_metadata(
            [{"name": "Ada Lovelace", "affiliation": "Analytical"}]
        )

        override_metadata = config.get_metadata_file()
        assert override_metadata != PandocOptions.METADATA_FILE
        contents = override_metadata.read_text(encoding="utf-8")
        assert "图 $$i$$$$titleDelim$$ $$t$$" in contents
        assert 'titleDelim: "："' in contents
        assert "Ada Lovelace" in contents


class TestPatternMatcher:
    """Test the PatternMatcher utility class."""
    
    def test_match_pattern_all(self):
        """Test pattern matching with 'all' mode."""
        content = "\\ref{fig1} and \\ref{fig2} and \\ref{fig3}"
        result = PatternMatcher.match_pattern(
            TexPatterns.REF,
            content,
            "all",
        )
        assert result == ["fig1", "fig2", "fig3"]
    
    def test_match_pattern_first(self):
        """Test pattern matching with 'first' mode."""
        content = "\\ref{fig1} and \\ref{fig2} and \\ref{fig3}"
        result = PatternMatcher.match_pattern(
            TexPatterns.REF,
            content,
            "first",
        )
        assert result == "fig1"
    
    def test_match_pattern_last(self):
        """Test pattern matching with 'last' mode."""
        content = "\\ref{fig1} and \\ref{fig2} and \\ref{fig3}"
        result = PatternMatcher.match_pattern(
            TexPatterns.REF,
            content,
            "last",
        )
        assert result == "fig3"
    
    def test_match_pattern_none(self):
        """Test pattern matching with no matches."""
        content = "No references here"
        result = PatternMatcher.match_pattern(
            TexPatterns.REF,
            content,
            "first",
        )
        assert result is None
    
    def test_match_pattern_invalid_mode(self):
        """Test pattern matching with invalid mode."""
        with pytest.raises(ValueError, match="mode must be"):
            PatternMatcher.match_pattern(
                TexPatterns.REF,
                "content",
                "invalid",
            )
    
    def test_find_figure_package_subfig(self):
        """Test detection of subfig package."""
        content = "\\usepackage{subfig}\\subfloat{content}"
        result = PatternMatcher.find_figure_package(content)
        assert result == "subfig"
    
    def test_find_figure_package_subfigure(self):
        """Test detection of subfigure package."""
        content = "\\usepackage{subfigure}\\subfigure{content}"
        result = PatternMatcher.find_figure_package(content)
        assert result == "subfigure"

    def test_find_figure_package_subcaption(self):
        """Test detection of subcaption package."""
        content = (
            "\\usepackage{subcaption}"
            "\\begin{subfigure}{0.5\\textwidth}content\\end{subfigure}"
        )
        result = PatternMatcher.find_figure_package(content)
        assert result == "subcaption"

    def test_find_figure_package_subcaption_environment(self):
        """Environment-only usage defaults to subcaption support."""
        content = "\\begin{subfigure}{0.5\\textwidth}content\\end{subfigure}"
        result = PatternMatcher.find_figure_package(content)
        assert result == "subcaption"
    
    def test_find_figure_package_none(self):
        """Test no figure package detection."""
        content = "\\usepackage{graphicx}"
        result = PatternMatcher.find_figure_package(content)
        assert result is None
    
    def test_has_chinese_characters(self):
        """Test Chinese character detection."""
        assert PatternMatcher.has_chinese_characters("这是中文")
        assert not PatternMatcher.has_chinese_characters("This is English")
        assert PatternMatcher.has_chinese_characters("Mixed 中文 content")
    
    def test_extract_graphicspath(self):
        """Test graphics path extraction."""
        content = "\\graphicspath{{figures/}}"
        result = PatternMatcher.extract_graphicspath(content)
        assert result == "figures/"
        entries = PatternMatcher.extract_graphicspaths(content)
        assert entries == ["figures/"]
        
        content_multi = "\\graphicspath{{figures/}{images/}}"
        result_multi = PatternMatcher.extract_graphicspath(content_multi)
        assert result_multi == "figures/"
        entries_multi = PatternMatcher.extract_graphicspaths(content_multi)
        assert entries_multi == ["figures/", "images/"]

    def test_extract_bibliography_files(self):
        """Bibliography commands yield normalized file hints."""
        content = (
            "\\bibliography{refs, extras}"
            "\\addbibresource[datatype=bibtex]{lib/library.bib}"
            "\\addbibresource{ ~/global.bib }"
        )

        result = PatternMatcher.extract_bibliography_files(content)

        assert result == [
            "refs",
            "extras",
            "lib/library.bib",
            "~/global.bib",
        ]


class TestTextProcessor:
    """Test the TextProcessor utility class."""
    
    def test_remove_comments(self):
        """Test comment removal."""
        content = "Line 1\n% This is a comment\nLine 2"
        result = TextProcessor.remove_comments(content)
        assert "% This is a comment" not in result
        assert "Line 1" in result
        assert "Line 2" in result
    
    def test_comment_out_captions(self):
        """Test caption commenting."""
        content = "\\caption{Test caption}"
        result = TextProcessor.comment_out_captions(content)
        assert result.startswith("% ")
    
    def test_remove_continued_float(self):
        """Test ContinuedFloat removal."""
        content = "\\ContinuedFloat\\caption{Test}"
        result = TextProcessor.remove_continued_float(content)
        assert "\\ContinuedFloat" not in result
        assert "\\caption{Test}" in result
    
    def test_sanitize_filename(self):
        """Test filename sanitization."""
        filename = "test:file*name?.tex"
        result = TextProcessor.sanitize_filename(filename)
        assert result == "test_file_name_.tex"


class TestContentModifier:
    """Test behaviour of the ContentModifier helper methods."""

    def _make_modifier(self, tmp_path: Path) -> ContentModifier:
        input_tex = tmp_path / "source.tex"
        input_tex.write_text("\\documentclass{article}\n\\begin{document}x\\end{document}")
        output_docx = tmp_path / "output.docx"
        config = ConversionConfig(
            input_texfile=input_tex,
            output_docxfile=output_docx,
            debug=True,
        )
        return ContentModifier(config)

    def test_updates_subfigure_refs_with_captions(self, tmp_path: Path) -> None:
        """Subfigure labels preceding captions are remapped with suffixes."""

        modifier = self._make_modifier(tmp_path)

        original = dedent(
            r"""
            \begin{figure}
                \begin{subfigure}{0.45\textwidth}
                \includegraphics{a.pdf}
                \caption{First}
                \label{fig:demo_a}
                \end{subfigure}
                \begin{subfigure}{0.45\textwidth}
                \includegraphics{b.pdf}
                \caption{Second}
                \label{fig:demo_b}
                \end{subfigure}
                \caption{Combined}
                \label{fig:demo}
            \end{figure}
            """
        )

        modifier.modified_content = (
            "See figure~\\ref{fig:demo_a} and figure~\\ref{fig:demo_b}. "
            "The overview is provided in figure~\\ref{fig:demo}."
        )

        modifier._update_subfigure_references(original, "fig:multifig_demo")
        modifier._update_main_reference(original, "fig:multifig_demo")

        assert "figure~\\ref{fig:multifig_demo}(a)" in modifier.modified_content
        assert "figure~\\ref{fig:multifig_demo}(b)" in modifier.modified_content
        assert "figure~\\ref{fig:multifig_demo}." in modifier.modified_content

    def test_normalizes_tab_prefix_labels(self, tmp_path: Path) -> None:
        """Legacy tab: prefixes are rewritten to tbl: counterparts."""

        modifier = self._make_modifier(tmp_path)
        modifier.modified_content = (
            "Table~\\ref{tab:legacy} lists values. "
            "\\begin{table}\\label{tab:legacy}\\end{table}"
        )

        modifier._normalize_table_labels()

        assert "Table~\\ref{tbl:legacy}" in modifier.modified_content
        assert "\\label{tbl:legacy}" in modifier.modified_content

    def test_normalize_table_rules_converts_booktabs(
        self, tmp_path: Path
    ) -> None:
        """Booktabs directives become standard hline rules."""

        modifier = self._make_modifier(tmp_path)
        modifier.modified_content = dedent(
            (
                "\\begin{table}\n"
                "\\centering\n"
                "\\begin{tabular}{lc}\n"
                "\\toprule\n"
                "Label & Value \\\\n"
                "\\midrule\n"
                "A & 1 \\\\n"
                "\\bottomrule\n"
                "\\end{tabular}\n"
                "\\end{table}\n"
            )
        )

        modifier._normalize_table_rules()

        assert "\\toprule" not in modifier.modified_content
        assert "\\midrule" not in modifier.modified_content
        assert "\\bottomrule" not in modifier.modified_content
        assert modifier.modified_content.count("\\hline") == 3

    def test_normalize_table_rules_adds_three_line_default(
        self, tmp_path: Path
    ) -> None:
        """Tables without rule markers receive three-line styling."""

        modifier = self._make_modifier(tmp_path)
        modifier.modified_content = dedent(
            (
                "\\begin{table}\n"
                "\\centering\n"
                "\\begin{tabular}{lc}\n"
                "Header & Value \\\\n"
                "Alpha & 1 \\\\n"
                "Beta & 2 \\\\n"
                "\\end{tabular}\n"
                "\\end{table}\n"
            )
        )

        modifier._normalize_table_rules()

        assert modifier.modified_content.count("\\hline") == 3
        first_rule = modifier.modified_content.find("\\hline")
        assert first_rule != -1
        header_pos = modifier.modified_content.find("Header")
        assert first_rule < header_pos

    def test_unwrap_resizebox_tabular(self, tmp_path: Path) -> None:
        """Resizebox wrappers around tables are removed."""

        modifier = self._make_modifier(tmp_path)
        modifier.modified_content = dedent(
            r"""
            \begin{table}[htbp]
            \centering
            \resizebox{\textwidth}{!}{
              \begin{tabular}{cc}
              A & B \\
              C & D \\
              \end{tabular}
            }
            \caption{Sample}
            \label{tbl:sample}
            \end{table}
            """
        )

        modifier._unwrap_resizebox_tabular()

        assert "\\resizebox" not in modifier.modified_content
        assert "\\begin{tabular}{cc}" in modifier.modified_content


class TestMathTextFilter:
    """Unit coverage for the inline math normalization filter."""

    FILTER_PATH = (
        Path(__file__).resolve().parent.parent
        / "tex2docx"
        / "math_text.lua"
    )

    @classmethod
    def _run_filter(cls, latex: str) -> Dict[str, object]:
        """Execute Pandoc with the math_text filter and return JSON."""

        command = [
            "pandoc",
            "-f",
            "latex",
            "-t",
            "json",
            "--lua-filter",
            str(cls.FILTER_PATH),
        ]

        result = subprocess.run(
            command,
            input=latex.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

        return json.loads(result.stdout.decode("utf-8"))

    @staticmethod
    def _extract_inlines(payload: Dict[str, object]) -> list:
        """Return the inline list from the first block of the payload."""

        blocks = payload.get("blocks", [])
        if not blocks:
            return []
        return blocks[0].get("c", [])

    def test_converts_simple_formula(self) -> None:
        """CO_{2} is rewritten as text plus a subscript."""

        payload = self._run_filter("$CO_{2}$")
        inlines = self._extract_inlines(payload)

        assert [inline["t"] for inline in inlines] == ["Str", "Subscript"]
        assert inlines[0]["c"] == "CO"
        assert inlines[1]["c"][0]["c"] == "2"

    def test_preserves_general_math(self) -> None:
        """Polynomial expressions remain math objects."""

        payload = self._run_filter("$a^2 + b^2$")
        inlines = self._extract_inlines(payload)

        assert len(inlines) == 1
        assert inlines[0]["t"] == "Math"

    def test_converts_nuclear_notation(self) -> None:
        """Nuclear isotope notation keeps upright glyphs."""

        payload = self._run_filter("$^{203}_{82}\\mathrm{Pb}$")
        inlines = self._extract_inlines(payload)

        assert [inline["t"] for inline in inlines] == [
            "Superscript",
            "Subscript",
            "Str",
        ]
        assert inlines[0]["c"][0]["c"] == "203"
        assert inlines[1]["c"][0]["c"] == "82"
        assert inlines[2]["c"] == "Pb"


class TestLatexParser:
    """Test the LatexParser class."""
    
    @pytest.fixture
    def sample_tex_content(self):
        """Sample LaTeX content for testing."""
        return """
        \\documentclass{article}
        \\usepackage{graphicx}
        \\usepackage{subfig}
        \\graphicspath{{figures/}}
        \\begin{document}
        \\begin{figure}
            \\centering
            \\includegraphics{test.png}
            \\caption{Test figure}
            \\label{fig:test}
        \\end{figure}
        \\begin{table}
            \\centering
            \\caption{Test table}
            \\label{tab:test}
            \\begin{tabular}{cc}
                A & B \\\\
                C & D
            \\end{tabular}
        \\end{table}
        \\end{document}
        """
    
    @pytest.fixture
    def config_with_temp_file(self, tmp_path, sample_tex_content):
        """Create a config with a temporary TeX file."""
        input_file = tmp_path / "test.tex"
        output_file = tmp_path / "test.docx"
        input_file.write_text(sample_tex_content)
        
        return ConversionConfig(
            input_texfile=input_file,
            output_docxfile=output_file,
            debug=True
        )
    
    def test_parser_initialization(self, config_with_temp_file):
        """Test parser initialization."""
        parser = LatexParser(config_with_temp_file)
        assert parser.config == config_with_temp_file
        assert parser.raw_content is None
        assert parser.clean_content is None
        assert parser.figure_contents == []
        assert parser.table_contents == []
    
    def test_read_and_preprocess(self, config_with_temp_file):
        """Test reading and preprocessing."""
        parser = LatexParser(config_with_temp_file)
        parser.read_and_preprocess()
        
        assert parser.raw_content is not None
        assert parser.clean_content is not None
        assert "\\documentclass{article}" in parser.clean_content
    
    def test_analyze_structure(self, config_with_temp_file):
        """Test structure analysis."""
        parser = LatexParser(config_with_temp_file)
        parser.read_and_preprocess()
        parser.analyze_structure()
        
        assert len(parser.figure_contents) == 1
        assert len(parser.table_contents) == 1
        assert parser.figure_package == "subfig"
        assert parser.graphicspath is not None
        assert not parser.contains_chinese
    
    def test_get_analysis_summary(self, config_with_temp_file):
        """Test analysis summary."""
        parser = LatexParser(config_with_temp_file)
        parser.read_and_preprocess()
        parser.analyze_structure()
        
        summary = parser.get_analysis_summary()
        assert summary["num_figures"] == 1
        assert summary["num_tables"] == 1
        assert summary["figure_package"] == "subfig"
        assert summary["contains_chinese"] is False
        assert summary["has_clean_content"] is True

    def test_detect_bibliography_from_addbibresource(
        self,
        tmp_path: Path,
    ) -> None:
        """Parser resolves bibliography files declared via addbibresource."""

        latex = dedent(
            r"""
            \documentclass{article}
            \usepackage{biblatex}
            \addbibresource{bib/refs.bib}
            \begin{document}
            \cite{smith2020}
            \printbibliography
            \end{document}
            """
        )

        input_tex = tmp_path / "paper.tex"
        input_tex.write_text(latex, encoding="utf-8")

        bib_dir = tmp_path / "bib"
        bib_dir.mkdir()
        bib_file = bib_dir / "refs.bib"
        bib_file.write_text("@article{smith2020, title={X}}", encoding="utf-8")

        output_file = tmp_path / "paper.docx"
        config = ConversionConfig(
            input_texfile=input_tex,
            output_docxfile=output_file,
            debug=True,
        )

        assert config.bibfile is None

        parser = LatexParser(config)
        parser.read_and_preprocess()
        parser.analyze_structure()

        assert config.bibfile == bib_file.resolve()
        assert config.get_bibliography_files() == [bib_file.resolve()]

    def test_detect_bibliography_from_bibliography_command(
        self,
        tmp_path: Path,
    ) -> None:
        """Parser resolves bibliography declared via bibliography command."""

        latex = dedent(
            r"""
            \documentclass{article}
            \begin{document}
            \cite{doe2019}
            \bibliography{sources/references}
            \bibliographystyle{IEEEtran}
            \end{document}
            """
        )

        input_tex = tmp_path / "chapter.tex"
        input_tex.write_text(latex, encoding="utf-8")

        sources_dir = tmp_path / "sources"
        sources_dir.mkdir()
        bib_file = sources_dir / "references.bib"
        bib_file.write_text("@book{doe2019, title={Y}}", encoding="utf-8")

        output_file = tmp_path / "chapter.docx"
        config = ConversionConfig(
            input_texfile=input_tex,
            output_docxfile=output_file,
        )

        assert config.bibfile is None

        parser = LatexParser(config)
        parser.read_and_preprocess()
        parser.analyze_structure()

        assert config.bibfile == bib_file.resolve()
        assert config.get_bibliography_files() == [bib_file.resolve()]

    def test_detect_bibliography_preserves_explicit_config(
        self,
        tmp_path: Path,
    ) -> None:
        """Parser keeps user-specified bibliography when already valid."""

        latex = dedent(
            r"""
            \documentclass{article}
            \usepackage{biblatex}
            \addbibresource{alt/extra.bib}
            \begin{document}
            \cite{roe2021}
            \end{document}
            """
        )

        input_tex = tmp_path / "main.tex"
        input_tex.write_text(latex, encoding="utf-8")

        preferred_bib = tmp_path / "preferred.bib"
        preferred_bib.write_text("@misc{roe2021, title={Z}}", encoding="utf-8")

        alt_dir = tmp_path / "alt"
        alt_dir.mkdir()
        alt_dir.joinpath("extra.bib").write_text(
            "@misc{alt, title={Alt}}",
            encoding="utf-8",
        )

        output_file = tmp_path / "main.docx"
        config = ConversionConfig(
            input_texfile=input_tex,
            output_docxfile=output_file,
            bibfile=preferred_bib,
        )

        assert config.bibfile == preferred_bib.resolve()

        parser = LatexParser(config)
        parser.read_and_preprocess()
        parser.analyze_structure()

        assert config.bibfile == preferred_bib.resolve()
        assert config.get_bibliography_files() == [
            preferred_bib.resolve(),
            (alt_dir / "extra.bib").resolve(),
        ]

    def test_detects_multiple_bibliography_files(
        self,
        tmp_path: Path,
    ) -> None:
        """Parser collects all bibliography declarations in source."""

        latex = dedent(
            r"""
            \documentclass{article}
            \usepackage{biblatex}
            \addbibresource{bib/refs}
            \begin{document}
            \cite{smith2020}
            \bibliography{extra/more}
            \printbibliography
            \end{document}
            """
        )

        input_tex = tmp_path / "combined.tex"
        input_tex.write_text(latex, encoding="utf-8")

        bib_dir = tmp_path / "bib"
        bib_dir.mkdir()
        first_bib = bib_dir / "refs.bib"
        first_bib.write_text(
            "@article{smith2020, title={X}}",
            encoding="utf-8",
        )

        extra_dir = tmp_path / "extra"
        extra_dir.mkdir()
        second_bib = extra_dir / "more.bib"
        second_bib.write_text(
            "@book{jones2018, title={Y}}",
            encoding="utf-8",
        )

        output_file = tmp_path / "combined.docx"
        config = ConversionConfig(
            input_texfile=input_tex,
            output_docxfile=output_file,
        )

        parser = LatexParser(config)
        parser.read_and_preprocess()
        parser.analyze_structure()

        collected = config.get_bibliography_files()
        assert config.bibfile == collected[0]
        assert set(collected) == {
            first_bib.resolve(),
            second_bib.resolve(),
        }
    
    def test_missing_file_error(self, tmp_path):
        """Test error when input file is missing."""
        input_file = tmp_path / "nonexistent.tex"
        output_file = tmp_path / "test.docx"
        
        with pytest.raises(FileNotFoundError):
            ConversionConfig(
                input_texfile=input_file,
                output_docxfile=output_file
            )


class TestConstants:
    """Test constants and templates."""
    
    def test_tex_patterns_defined(self):
        """Test that all required patterns are defined."""
        assert hasattr(TexPatterns, 'FIGURE')
        assert hasattr(TexPatterns, 'TABLE')
        assert hasattr(TexPatterns, 'CAPTION')
        assert hasattr(TexPatterns, 'LABEL')
        assert hasattr(TexPatterns, 'REF')
        assert hasattr(TexPatterns, 'GRAPHICSPATH')
        assert hasattr(TexPatterns, 'INCLUDEGRAPHICS')
        assert hasattr(TexPatterns, 'COMMENT')
        assert hasattr(TexPatterns, 'CHINESE_CHAR')
    
    def test_tex_templates_defined(self):
        """Test that all required templates are defined."""
        assert hasattr(TexTemplates, 'BASE_MULTIFIG_TEXFILE')
        assert hasattr(TexTemplates, 'MULTIFIG_FIGENV')
        assert hasattr(TexTemplates, 'MODIFIED_TABENV')
        
        # Check that templates contain expected placeholders
        assert "FIGURE_CONTENT_PLACEHOLDER" in (
            TexTemplates.BASE_MULTIFIG_TEXFILE
        )
        assert "GRAPHICSPATH_PLACEHOLDER" in TexTemplates.BASE_MULTIFIG_TEXFILE
        assert "%s" in TexTemplates.MULTIFIG_FIGENV
        assert "%s" in TexTemplates.MODIFIED_TABENV


class TestIntegration:
    """Integration tests for the complete workflow."""
    
    @pytest.fixture
    def minimal_tex_file(self, tmp_path):
        """Create a minimal TeX file for testing."""
        content = """
        \\documentclass{article}
        \\usepackage{graphicx}
        \\begin{document}
        Hello World!
        \\begin{figure}
            \\centering
            \\includegraphics[width=0.5\\textwidth]{example.png}
            \\caption{Example figure}
            \\label{fig:example}
        \\end{figure}
        See Figure \\ref{fig:example}.
        \\end{document}
        """
        tex_file = tmp_path / "minimal.tex"
        tex_file.write_text(content)
        return tex_file
    
    def test_config_creation_and_validation(self, minimal_tex_file, tmp_path):
        """Test configuration creation and validation."""
        output_file = tmp_path / "output.docx"
        
        # This should work without raising exceptions
        config = ConversionConfig(
            input_texfile=minimal_tex_file,
            output_docxfile=output_file,
            debug=True
        )
        
        assert config.input_texfile.exists()
        assert config.output_texfile is not None
        assert config.temp_subtexfile_dir is not None
    
    @patch('shutil.which')
    def test_dependency_checking(self, mock_which, minimal_tex_file, tmp_path):
        """Test dependency checking."""
        from tex2docx.converter import PandocConverter
        
        config = ConversionConfig(
            input_texfile=minimal_tex_file,
            output_docxfile=tmp_path / "output.docx",
            debug=True
        )
        
        converter = PandocConverter(config)
        
        # Test when pandoc is missing
        mock_which.return_value = None
        with pytest.raises(Exception):  # DependencyError
            converter._check_dependencies()
        
        # Test when pandoc is available
        mock_which.return_value = "/usr/bin/pandoc"
        # Should not raise exception
        converter._check_dependencies()


# Test fixtures for common use cases
@pytest.fixture
def temp_dir():
    """Provide a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_config(temp_dir):
    """Provide a sample configuration for testing."""
    input_file = temp_dir / "test.tex"
    output_file = temp_dir / "test.docx"
    
    # Create a minimal valid TeX file
    input_file.write_text("""
    \\documentclass{article}
    \\begin{document}
    Test document
    \\end{document}
    """)
    
    return ConversionConfig(
        input_texfile=input_file,
        output_docxfile=output_file,
        debug=True
    )


class TestPandocConverterRuntime:
    """Runtime-focused tests for Pandoc converter helpers."""

    def test_run_pandoc_uses_timeout(self, sample_config, monkeypatch):
        """Pandoc subprocess is invoked with the configured timeout."""

        sample_config.output_texfile.write_text("\n")
        converter = PandocConverter(sample_config)

        command = [
            "pandoc",
            sample_config.output_texfile.name,
            "-o",
            sample_config.output_docxfile.name,
        ]

        completed = subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="ok",
            stderr="",
        )

        captured: Dict[str, object] = {}

        def fake_run(*args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            captured["cwd"] = kwargs.get("cwd")
            return completed

        monkeypatch.setattr(subprocess, "run", fake_run)

        converter._run_pandoc(command)

        assert captured["timeout"] == PandocOptions.TIMEOUT
        assert captured["cwd"] == sample_config.output_texfile.parent

    def test_run_pandoc_timeout_raises_conversion_error(
        self,
        sample_config,
        monkeypatch,
    ) -> None:
        """Timeouts from pandoc raise a ConversionError with context."""

        sample_config.output_texfile.write_text("\n")
        converter = PandocConverter(sample_config)

        command = [
            "pandoc",
            sample_config.output_texfile.name,
            "-o",
            sample_config.output_docxfile.name,
        ]

        def fake_run(*args, **kwargs):
            raise subprocess.TimeoutExpired(
                cmd=args[0],
                timeout=kwargs.get("timeout"),
                output="pending",
                stderr="late",
            )

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(ConversionError, match="timed out"):
            converter._run_pandoc(command)



class TestDocxTableStyling:
    """Tests for DOCX table styling helpers."""

    def test_style_docx_table_creates_three_line_rules(self) -> None:
        """Tables receive top, header, and bottom borders."""

        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        namespaces = {"w": ns}
        tbl = ET.Element(f"{{{ns}}}tbl")
        ET.SubElement(tbl, f"{{{ns}}}tr")

        modified = PandocConverter._style_docx_table(tbl, namespaces)

        assert modified is True
        tbl_borders = tbl.find("w:tblPr/w:tblBorders", namespaces)
        assert tbl_borders is not None

        for position in ("top", "bottom"):
            border = tbl_borders.find(f"w:{position}", namespaces)
            assert border is not None
            assert border.attrib[f"{{{ns}}}val"] == "single"
            assert border.attrib[f"{{{ns}}}sz"] == "12"

        header_border = tbl.find(
            "w:tr/w:trPr/w:trBorders/w:bottom",
            namespaces,
        )
        assert header_border is not None
        assert header_border.attrib[f"{{{ns}}}val"] == "single"
        assert header_border.attrib[f"{{{ns}}}sz"] == "12"

    def test_style_docx_table_idempotent(self) -> None:
        """Repeated styling calls keep borders stable."""

        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        namespaces = {"w": ns}
        tbl = ET.Element(f"{{{ns}}}tbl")
        ET.SubElement(tbl, f"{{{ns}}}tr")

        PandocConverter._style_docx_table(tbl, namespaces)
        modified = PandocConverter._style_docx_table(tbl, namespaces)

        assert modified is False
        top_border = tbl.find("w:tblPr/w:tblBorders/w:top", namespaces)
        assert top_border is not None
        assert top_border.attrib[f"{{{ns}}}val"] == "single"
        assert top_border.attrib[f"{{{ns}}}color"] == "auto"


class TestSubfileCompilerRuntime:
    """Tests focused on subfile compilation orchestration."""

    @staticmethod
    def _build_config(tmp_path: Path) -> ConversionConfig:
        input_file = tmp_path / "main.tex"
        output_file = tmp_path / "main.docx"
        input_file.write_text(
            "\\documentclass{article}\\begin{document}x\\end{document}"
        )
        return ConversionConfig(
            input_texfile=input_file,
            output_docxfile=output_file,
            debug=True,
        )

    def test_compile_parallel_uses_spawn_context(self, tmp_path, monkeypatch):
        """Compilation uses spawn context to avoid fork-related hangs."""

        config = self._build_config(tmp_path)
        compiler = SubfileCompiler(config)
        file_paths = [config.temp_subtexfile_dir / "one.tex"]

        calls: Dict[str, object] = {}

        def fake_get_context(method=None) -> str:
            calls.setdefault("methods", []).append(method)
            if method == "spawn":
                return "sentinel-context"
            return "default-context"

        class DummyFuture:
            def __init__(self, result: bool) -> None:
                self._result = result

            def result(self) -> bool:
                return self._result

            def __hash__(self) -> int:
                return id(self)

        class DummyExecutor:
            def __init__(self, *args, **kwargs) -> None:
                calls["executor_kwargs"] = kwargs
                DummyExecutor.submissions = []

            def __enter__(self) -> "DummyExecutor":
                return self

            def __exit__(self, *exc_info) -> bool:
                return False

            def submit(self, fn, path):
                DummyExecutor.submissions.append(path)
                return DummyFuture(True)

        def fake_as_completed(futures):
            return list(futures)

        def passthrough_tqdm(iterable, **kwargs):
            return iterable

        monkeypatch.setattr(subfile_module.mp, "get_context", fake_get_context)
        monkeypatch.setattr(
            subfile_module.concurrent.futures,
            "ProcessPoolExecutor",
            DummyExecutor,
        )
        monkeypatch.setattr(
            subfile_module.concurrent.futures,
            "as_completed",
            fake_as_completed,
        )
        monkeypatch.setattr(subfile_module, "tqdm", passthrough_tqdm)

        successful, failed = compiler._compile_parallel(file_paths)

        assert successful == 1
        assert failed == []
        assert calls["methods"] == ["spawn"]
        assert calls["executor_kwargs"]["mp_context"] == "sentinel-context"
        assert calls["executor_kwargs"]["max_workers"] == 1
        assert DummyExecutor.submissions == file_paths

    def test_compile_parallel_collects_failures(self, tmp_path, monkeypatch):
        """Failures and exceptions from workers are aggregated."""

        config = self._build_config(tmp_path)
        compiler = SubfileCompiler(config)
        file_paths = [
            config.temp_subtexfile_dir / "ok.tex",
            config.temp_subtexfile_dir / "fail.tex",
        ]

        outcomes = [True, RuntimeError("boom")]

        class DummyFuture:
            def __init__(self, outcome) -> None:
                self._outcome = outcome

            def result(self):
                if isinstance(self._outcome, Exception):
                    raise self._outcome
                return self._outcome

            def __hash__(self) -> int:
                return id(self)

        class DummyExecutor:
            def __init__(self, *args, **kwargs) -> None:
                DummyExecutor.submissions = []

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def submit(self, fn, path):
                DummyExecutor.submissions.append(path)
                outcome = outcomes.pop(0)
                return DummyFuture(outcome)

        def fake_as_completed(futures):
            return list(futures)

        def passthrough_tqdm(iterable, **kwargs):
            return iterable

        monkeypatch.setattr(
            subfile_module.concurrent.futures,
            "ProcessPoolExecutor",
            DummyExecutor,
        )
        monkeypatch.setattr(
            subfile_module.mp,
            "get_context",
            lambda method=None: "ctx" if method == "spawn" else "ctx-default",
        )
        monkeypatch.setattr(
            subfile_module.concurrent.futures,
            "as_completed",
            fake_as_completed,
        )
        monkeypatch.setattr(subfile_module, "tqdm", passthrough_tqdm)

        successful, failed = compiler._compile_parallel(file_paths)

        assert successful == 1
        assert failed == ["fail.tex"]
        assert DummyExecutor.submissions == file_paths

    def test_compile_parallel_falls_back_when_main_missing(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """Fallback context is used when the main module path is absent."""

        config = self._build_config(tmp_path)
        compiler = SubfileCompiler(config)
        file_paths = [config.temp_subtexfile_dir / "only.tex"]

        monkeypatch.setattr(subfile_module.sys, "argv", ["<stdin>"])

        calls: Dict[str, object] = {}

        def fake_get_context(method=None):
            calls.setdefault("methods", []).append(method)
            return "default-context"

        class DummyFuture:
            def __init__(self, result: bool) -> None:
                self._result = result

            def result(self) -> bool:
                return self._result

            def __hash__(self) -> int:
                return id(self)

        class DummyExecutor:
            def __init__(self, *args, **kwargs) -> None:
                calls["executor_kwargs"] = kwargs

            def __enter__(self) -> "DummyExecutor":
                return self

            def __exit__(self, *exc_info) -> bool:
                return False

            def submit(self, fn, path):
                return DummyFuture(True)

        def fake_as_completed(futures):
            return list(futures)

        def passthrough_tqdm(iterable, **kwargs):
            return iterable

        monkeypatch.setattr(
            subfile_module.mp,
            "get_context",
            fake_get_context,
        )
        monkeypatch.setattr(
            subfile_module.concurrent.futures,
            "ProcessPoolExecutor",
            DummyExecutor,
        )
        monkeypatch.setattr(
            subfile_module.concurrent.futures,
            "as_completed",
            fake_as_completed,
        )
        monkeypatch.setattr(subfile_module, "tqdm", passthrough_tqdm)

        successful, failed = compiler._compile_parallel(file_paths)

        assert successful == 1
        assert failed == []
        assert calls["methods"] == [None]
        assert calls["executor_kwargs"]["mp_context"] == "default-context"


# Performance and stress tests
class TestConverterPreferences:
    """Converter-level preference wiring tests."""

    def test_converter_applies_caption_locale_and_author(self, tmp_path):
        """Converter propagates locale and author metadata to config."""

        input_file = tmp_path / "pref.tex"
        output_file = tmp_path / "pref.docx"
        input_file.write_text(
            "\\documentclass{article}"
            "\\begin{document}x\\end{document}"
        )

        converter = LatexToWordConverter(
            input_texfile=input_file,
            output_docxfile=output_file,
            caption_locale="zh",
            author_metadata=[{"name": "Ada Lovelace"}],
        )

        config = converter.config
        assert config.caption_style.fig_prefix[0] == "图"
        assert config.author_metadata is not None
        assert config.author_metadata["author"] == [{"name": "Ada Lovelace"}]
        assert config.author_metadata["institute"] == []

        active_filters = config.get_lua_filters()
        expected_filters = config.author_lua_filters + config.lua_filters
        assert [path.resolve() for path in active_filters] == [
            path.resolve() for path in expected_filters
        ]

        metadata_path = config.get_metadata_file()
        assert metadata_path != PandocOptions.METADATA_FILE
        metadata_text = metadata_path.read_text(encoding="utf-8")
        assert "Ada Lovelace" in metadata_text

    def test_converter_without_author_uses_base_filters(self, tmp_path):
        """Base Lua filters apply when no author metadata is present."""

        input_file = tmp_path / "no_author.tex"
        output_file = tmp_path / "no_author.docx"
        input_file.write_text(
            "\\documentclass{article}" "\\begin{document}x\\end{document}"
        )

        converter = LatexToWordConverter(
            input_texfile=input_file,
            output_docxfile=output_file,
        )

        config = converter.config
        assert not config.has_author_metadata()
        assert config.get_lua_filters() == config.lua_filters

        metadata_path = config.get_metadata_file()
        assert metadata_path == PandocOptions.METADATA_FILE
        assert metadata_path.exists()


class TestAuthorMetadata:
    """Author metadata extraction and synchronization tests."""

    def test_parse_author_metadata_with_affiliations(self) -> None:
        """Authblk-style authors produce structured metadata."""

        content = (
            "\\author[1$\\dag$]{Author A\\thanks{Funded by XYZ}}\n"
            "\\author[1]{Author B}\n"
            "\\author[1*]{Author C}\n"
            "\\affil[1]{Department of Examples}\n"
            "\\affil[*]{Contact: mail@example.com}\n"
            "\\affil[$\\dag$]{These authors contributed equally.}\n"
        )

        metadata = parse_author_metadata(content)

        assert metadata is not None
        assert isinstance(metadata, dict)

        authors = metadata.get("author")
        institutes = metadata.get("institute")

        assert isinstance(authors, list)
        assert isinstance(institutes, list)
        assert len(authors) == 3
        assert authors[0]["name"] == "Author A"
        assert authors[1]["name"] == "Author B"
        assert authors[2]["name"] == "Author C"

        author_a = authors[0]
        assert author_a.get("institute") == ["affiliation-1"]
        assert "Funded by XYZ" in author_a.get("note", "")
        assert "These authors contributed equally" in author_a.get("note", "")

        author_b = authors[1]
        assert "note" not in author_b

        author_c = authors[2]
        assert "mail@example.com" in author_c.get("note", "")

        assert len(institutes) == 1
        assert institutes[0]["name"] == "Department of Examples"

    def test_parser_captures_author_metadata(self, temp_dir: Path) -> None:
        """Parser stores author list when detected."""

        tex_path = temp_dir / "authors.tex"
        tex_path.write_text(
            "\n".join(
                [
                    "\\documentclass{article}",
                    "\\title{Sample Title}",
                    "\\author{Author One \\and Author Two}",
                    "\\begin{document}",
                    "\\maketitle",
                    "\\end{document}",
                ]
            ),
            encoding="utf-8",
        )

        config = ConversionConfig(
            input_texfile=tex_path,
            output_docxfile=temp_dir / "out.docx",
        )

        parser = LatexParser(config)
        parser.read_and_preprocess()
        parser.analyze_structure()

        assert parser.author_metadata is not None
        assert isinstance(parser.author_metadata, dict)
        assert parser.author_metadata["author"] == [
            {"name": "Author One"},
            {"name": "Author Two"},
        ]
        assert parser.author_metadata["institute"] == []

    def test_sync_author_metadata_respects_manual_overrides(
        self, temp_dir: Path
    ) -> None:
        """Manual metadata stays in config when present."""

        tex_path = temp_dir / "authors_override.tex"
        tex_path.write_text(
            "\n".join(
                [
                    "\\documentclass{article}",
                    "\\title{Override Sample}",
                    "\\author{Auto One \\and Auto Two}",
                    "\\begin{document}",
                    "\\maketitle",
                    "\\end{document}",
                ]
            ),
            encoding="utf-8",
        )

        manual_metadata = [
            {"name": "Manual Person", "affiliation": "Org"}
        ]

        converter = LatexToWordConverter(
            input_texfile=tex_path,
            output_docxfile=temp_dir / "override.docx",
            author_metadata=manual_metadata,
        )

        parser = LatexParser(converter.config)
        parser.read_and_preprocess()
        parser.analyze_structure()

        converter._sync_author_metadata(parser)

        metadata = converter.config.author_metadata
        assert metadata is not None
        assert isinstance(metadata, dict)
        authors = metadata["author"]
        assert isinstance(authors, list)
        assert len(authors) == 1
        author_entry = authors[0]
        assert isinstance(author_entry, dict)
        assert author_entry["name"] == "Manual Person"
        institute_ids = author_entry["institute"]
        assert isinstance(institute_ids, list)
        assert institute_ids == ["affiliation-1"]

        institutes = metadata["institute"]
        assert isinstance(institutes, list)
        assert len(institutes) == 1
        institute_entry = institutes[0]
        assert isinstance(institute_entry, dict)
        assert institute_entry["id"] == "affiliation-1"
        assert institute_entry["name"] == "Org"


# Performance and stress tests
class TestPerformance:
    """Performance and stress tests."""
    
    def test_large_document_parsing(self, temp_dir):
        """Test parsing of a large document."""
        # Create a document with many figures
        content_parts = ["\\documentclass{article}", "\\begin{document}"]
        
        for i in range(50):  # 50 figures
            content_parts.append(f"""
            \\begin{{figure}}
                \\centering
                \\includegraphics{{fig{i}.png}}
                \\caption{{Figure {i}}}
                \\label{{fig:test{i}}}
            \\end{{figure}}
            """)
        
        content_parts.append("\\end{document}")
        content = "\n".join(content_parts)
        
        input_file = temp_dir / "large.tex"
        output_file = temp_dir / "large.docx"
        input_file.write_text(content)
        
        config = ConversionConfig(
            input_texfile=input_file,
            output_docxfile=output_file,
            debug=True
        )
        
        parser = LatexParser(config)
        parser.read_and_preprocess()
        parser.analyze_structure()
        
        # Should find all 50 figures
        assert len(parser.figure_contents) == 50
        
        summary = parser.get_analysis_summary()
        assert summary["num_figures"] == 50


class TestMCPServer:
    """Tests for the MCP server integration."""

    def test_convert_latex_to_docx_default_output(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        """Server uses the default DOCX path when none is provided."""

        tex_path = tmp_path / "sample.tex"
        tex_path.write_text(
            "\\documentclass{article}"
            "\\begin{document}Example\\end{document}"
        )

        captured: Dict[str, Path] = {}

        def fake_convert(
            input_path: Path,
            output_path: Path,
            *,
            caption_locale: Optional[str],
            author_metadata: Optional[YamlValue],
            bibfile: Optional[Path],
            cslfile: Optional[Path],
            reference_docfile: Optional[Path],
            fix_table: bool,
        ) -> str:
            captured["input"] = input_path
            captured["output"] = output_path
            output_path.write_text("placeholder")
            return str(output_path)

        monkeypatch.setattr(
            mcp_server,
            "_convert_tex_to_docx_sync",
            fake_convert,
        )

        result = asyncio.run(
            mcp_server.convert_latex_to_docx(str(tex_path))
        )

        expected_output = tex_path.with_suffix(".docx").resolve()
        assert captured["input"] == tex_path.resolve()
        assert captured["output"] == expected_output
        assert result == str(expected_output)

    def test_convert_latex_to_docx_missing_input(self) -> None:
        """Server rejects missing input files."""

        missing_path = Path("/tmp/does-not-exist.tex")
        assert not missing_path.exists()

        with pytest.raises(ValueError, match="Input TeX file not found"):
            asyncio.run(
                mcp_server.convert_latex_to_docx(str(missing_path))
            )

    def test_convert_latex_to_docx_custom_output(self, monkeypatch, tmp_path):
        """Server respects explicit output paths and options."""

        tex_path = tmp_path / "input.tex"
        tex_path.write_text(
            "\\documentclass{article}"
            "\\begin{document}Example\\end{document}"
        )

        output_path = tmp_path / "nested" / "result.docx"
        metadata = [{"name": "Grace"}]

        captured: Dict[str, object] = {}

        # Ensure the output directory does not exist before invocation.
        assert not output_path.parent.exists()

        def fake_convert(
            input_path: Path,
            output_path: Path,
            *,
            caption_locale: Optional[str],
            author_metadata: Optional[YamlValue],
            bibfile: Optional[Path],
            cslfile: Optional[Path],
            reference_docfile: Optional[Path],
            fix_table: bool,
        ) -> str:
            captured["input"] = input_path
            captured["output"] = output_path
            captured["caption_locale"] = caption_locale
            captured["author_metadata"] = author_metadata
            captured["fix_table"] = fix_table
            output_path.write_text("placeholder")
            return str(output_path)

        monkeypatch.setattr(
            mcp_server,
            "_convert_tex_to_docx_sync",
            fake_convert,
        )

        result = asyncio.run(
            mcp_server.convert_latex_to_docx(
                str(tex_path),
                str(output_path),
                caption_locale="zh",
                author_metadata=metadata,
                fix_table=False,
            )
        )

        expected_output = output_path.resolve()
        assert expected_output.exists()
        assert captured["input"] == tex_path.resolve()
        assert captured["output"] == expected_output
        assert captured["caption_locale"] == "zh"
        assert captured["author_metadata"] == metadata
        assert captured["fix_table"] is False
        assert result == str(expected_output)

    def test_convert_latex_to_docx_rejects_directory(self, tmp_path) -> None:
        """Server rejects directory inputs with a helpful error."""

        directory_path = tmp_path / "subdir"
        directory_path.mkdir()

        with pytest.raises(ValueError, match="Input path is not a file"):
            asyncio.run(
                mcp_server.convert_latex_to_docx(str(directory_path))
            )

    def test_convert_latex_to_docx_resolves_optional_paths(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        """Optional asset paths are resolved before conversion."""

        tex_path = tmp_path / "paths.tex"
        tex_path.write_text(
            "\\documentclass{article}"
            "\\begin{document}Paths\\end{document}"
        )

        bibfile = tmp_path / "refs.bib"
        bibfile.write_text("@book{key, title={Book}}")
        cslfile = tmp_path / "style.csl"
        cslfile.write_text("dummy")
        ref_doc = tmp_path / "ref.docx"
        ref_doc.write_bytes(b"placeholder")

        captured: Dict[str, Optional[Path]] = {}

        def fake_convert(
            input_path: Path,
            output_path: Path,
            *,
            caption_locale: Optional[str],
            author_metadata: Optional[YamlValue],
            bibfile: Optional[Path],
            cslfile: Optional[Path],
            reference_docfile: Optional[Path],
            fix_table: bool,
        ) -> str:
            captured["bibfile"] = bibfile
            captured["cslfile"] = cslfile
            captured["reference_docfile"] = reference_docfile
            output_path.write_text("placeholder")
            return str(output_path)

        monkeypatch.setattr(
            mcp_server,
            "_convert_tex_to_docx_sync",
            fake_convert,
        )

        result = asyncio.run(
            mcp_server.convert_latex_to_docx(
                str(tex_path),
                bibfile=str(bibfile),
                cslfile=str(cslfile),
                reference_docfile=str(ref_doc),
            )
        )

        assert captured["bibfile"] == bibfile.resolve()
        assert captured["cslfile"] == cslfile.resolve()
        assert captured["reference_docfile"] == ref_doc.resolve()
        assert Path(result).exists()

    def test_convert_latex_to_docx_wraps_tex2docx_error(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        """Underlying Tex2DocxError surfaces as RuntimeError for MCP."""

        tex_path = tmp_path / "fails.tex"
        tex_path.write_text(
            "\\documentclass{article}"
            "\\begin{document}Fail\\end{document}"
        )

        def fake_convert(
            input_path: Path,
            output_path: Path,
            *,
            caption_locale: Optional[str],
            author_metadata: Optional[YamlValue],
            bibfile: Optional[Path],
            cslfile: Optional[Path],
            reference_docfile: Optional[Path],
            fix_table: bool,
        ) -> str:
            raise Tex2DocxError("boom")

        monkeypatch.setattr(
            mcp_server,
            "_convert_tex_to_docx_sync",
            fake_convert,
        )

        with pytest.raises(RuntimeError, match="Conversion failed: boom"):
            asyncio.run(
                mcp_server.convert_latex_to_docx(str(tex_path))
            )


if __name__ == "__main__":
    pytest.main([__file__])
