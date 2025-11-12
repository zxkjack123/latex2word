"""Model Context Protocol server for tex2docx conversion."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .config import YamlValue
from .exceptions import Tex2DocxError
from .tex2docx import LatexToWordConverter

LOGGER = logging.getLogger(__name__)

mcp = FastMCP("tex2docx")


def _convert_tex_to_docx_sync(
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
    """Run the synchronous conversion workflow."""
    converter = LatexToWordConverter(
        input_texfile=input_path,
        output_docxfile=output_path,
        bibfile=bibfile,
        cslfile=cslfile,
        reference_docfile=reference_docfile,
        caption_locale=caption_locale,
        fix_table=fix_table,
        author_metadata=author_metadata,
    )
    converter.convert()
    return str(output_path)


@mcp.tool()
async def convert_latex_to_docx(
    tex_path: str,
    output_path: Optional[str] = None,
    caption_locale: Optional[str] = None,
    author_metadata: Optional[YamlValue] = None,
    bibfile: Optional[str] = None,
    cslfile: Optional[str] = None,
    reference_docfile: Optional[str] = None,
    fix_table: bool = False,
) -> str:
    """Convert a LaTeX document to a DOCX file."""
    input_path = Path(tex_path).expanduser().resolve()
    if not input_path.exists():
        raise ValueError(f"Input TeX file not found: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")

    if output_path is None:
        output = input_path.with_suffix(".docx")
    else:
        output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    resolved_bib = Path(bibfile).expanduser().resolve() if bibfile else None
    resolved_csl = Path(cslfile).expanduser().resolve() if cslfile else None
    resolved_reference = (
        Path(reference_docfile).expanduser().resolve()
        if reference_docfile
        else None
    )

    try:
        return await asyncio.to_thread(
            _convert_tex_to_docx_sync,
            input_path,
            output,
            caption_locale=caption_locale,
            author_metadata=author_metadata,
            bibfile=resolved_bib,
            cslfile=resolved_csl,
            reference_docfile=resolved_reference,
            fix_table=fix_table,
        )
    except Tex2DocxError as exc:
        LOGGER.error("Conversion failed: %s", exc)
        raise RuntimeError(f"Conversion failed: {exc}") from exc


def main() -> None:
    """Run the tex2docx MCP server."""
    LOGGER.info("Starting tex2docx MCP server")
    mcp.run(transport="stdio")


__all__ = ["mcp", "convert_latex_to_docx", "main"]


if __name__ == "__main__":
    main()
