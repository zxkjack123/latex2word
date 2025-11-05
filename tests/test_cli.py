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
