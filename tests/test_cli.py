"""CLI tests for user-facing error handling."""

from typer.testing import CliRunner

from tex2docx.cli import app


def test_cli_reports_tex2docx_error(tmp_path):
    """CLI exits with message when converter raises Tex2DocxError."""
    work_dir = tmp_path / "missing_cli"
    work_dir.mkdir()
    (work_dir / "figs").mkdir()

    tex_content = (
        "\\documentclass{article}\n"
        "\\usepackage{graphicx}\n"
        "\\graphicspath{{./figs/}}\n"
        "\\begin{document}\n"
        "\\begin{figure}\n"
        "    \\includegraphics{nonexistent}\n"
        "\\end{figure}\n"
        "\\end{document}\n"
    )
    input_tex = work_dir / "main.tex"
    input_tex.write_text(tex_content, encoding="utf-8")
    output_docx = work_dir / "main.docx"

    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        app,
        [
            "convert",
            "--input-texfile",
            str(input_tex),
            "--output-docxfile",
            str(output_docx),
            "--debug",
        ],
    )

    assert result.exit_code == 1
    assert "Conversion failed" in result.stderr
    assert "Missing graphic assets" in result.stderr
    assert not output_docx.exists()


def test_cli_caption_locale_and_authors(monkeypatch, tmp_path):
    """CLI passes caption locale and author metadata to converter."""

    captured = {}

    class StubConverter:  # pragma: no cover - exercised via CLI path
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

        def convert(self) -> None:
            return None

    monkeypatch.setattr("tex2docx.cli.LatexToWordConverter", StubConverter)

    input_tex = tmp_path / "input.tex"
    input_tex.write_text(
        "\\documentclass{article}"
        "\\begin{document}x\\end{document}"
    )
    output_docx = tmp_path / "output.docx"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "convert",
            "--input-texfile",
            str(input_tex),
            "--output-docxfile",
            str(output_docx),
            "--caption-locale",
            "zh",
            "--author",
            '{"name": "Ada Lovelace", "affiliation": "Analytical Engine"}',
            "--author",
            "name=Charles Babbage;affiliation=Cambridge University",
            "--author",
            "Grace Hopper",
        ],
    )

    assert result.exit_code == 0
    kwargs = captured["kwargs"]
    assert kwargs["caption_locale"] == "zh"
    authors = kwargs["author_metadata"]
    assert isinstance(authors, list)
    assert authors[0]["name"] == "Ada Lovelace"
    assert authors[1]["affiliation"] == "Cambridge University"
    assert authors[2] == "Grace Hopper"
