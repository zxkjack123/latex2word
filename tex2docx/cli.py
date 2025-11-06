import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import typer

from tex2docx import LatexToWordConverter
from tex2docx.config import YamlValue
from tex2docx.exceptions import Tex2DocxError

app = typer.Typer()


def _parse_kv_entry(entry: str) -> Optional[Dict[str, str]]:
    """Parse semicolon-delimited key=value pairs."""
    pairs: List[Tuple[str, str]] = []
    for segment in entry.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        if "=" not in segment:
            return None
        key, value = segment.split("=", 1)
        pairs.append((key.strip(), value.strip()))

    if not pairs:
        return None

    return {key: value for key, value in pairs}


def _parse_author_entry(entry: str) -> Optional[YamlValue]:
    """Interpret a single --author option value."""
    cleaned = entry.strip()
    if not cleaned:
        return None

    try:
        parsed: YamlValue = json.loads(cleaned)
    except json.JSONDecodeError:
        mapping = _parse_kv_entry(cleaned)
        if mapping is not None:
            return mapping
        return cleaned

    if isinstance(parsed, (dict, list, str, int, float, bool)):
        return parsed

    raise typer.BadParameter(
        "Author entries must decode to a string, mapping, list, or scalar."
    )


def _read_author_metadata_file(path: str) -> YamlValue:
    """Read author metadata from a JSON file."""
    try:
        payload = Path(path).read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - exercised in CLI
        raise typer.BadParameter(
            f"Failed to read author metadata file: {path}"
        ) from exc

    try:
        data: YamlValue = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(
            "Author metadata file must contain valid JSON."
        ) from exc

    if not isinstance(data, (dict, list, str, int, float, bool)):
        raise typer.BadParameter(
            "Author metadata file must decode to a JSON object, array, or "
            "scalar."
        )

    return data


def _collect_author_metadata(
    author_entries: Iterable[str],
    author_metadata_file: Optional[str],
) -> Optional[YamlValue]:
    """Combine inline and file-based author metadata."""
    items: List[YamlValue] = []

    if author_metadata_file:
        items.append(_read_author_metadata_file(author_metadata_file))

    for entry in author_entries:
        parsed = _parse_author_entry(entry)
        if parsed is None:
            continue
        items.append(parsed)

    if not items:
        return None

    flattened: List[YamlValue] = []
    for item in items:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)

    if not flattened:
        return None
    if len(flattened) == 1:
        return flattened[0]
    return flattened


# Subcommand for conversion
@app.command("convert")
def convert(
    input_texfile: str = typer.Option(
        ...,
        help="The path to the input LaTeX file.",
    ),
    output_docxfile: str = typer.Option(
        ...,
        help="The path to the output Word document.",
    ),
    reference_docfile: str = typer.Option(
        None,
        help=(
            "The path to the reference Word document. Defaults to None "
            "(use the built-in default_temp.docx file)."
        ),
    ),
    bibfile: str = typer.Option(
        None,
        help=(
            "The path to the BibTeX file. Defaults to None (use the first "
            ".bib file found in the same directory as input_texfile)."
        ),
    ),
    cslfile: str = typer.Option(
        None,
        help=(
            "The path to the CSL file. Defaults to None (use the "
            "built-in ieee.csl file)."
        ),
    ),
    caption_locale: Optional[str] = typer.Option(
        None,
        help=(
            "Locale for figure and table captions (e.g., 'en', 'zh'). "
            "Defaults to English."
        ),
    ),
    authors: Optional[List[str]] = typer.Option(
        None,
        "--author",
        help=(
            "Author metadata as JSON, semicolon-delimited key=value pairs, "
            "or plain names. Repeat to add multiple authors."
        ),
    ),
    author_metadata_file: Optional[str] = typer.Option(
        None,
        help=(
            "Path to a JSON file describing authors (object or array)."
        ),
    ),
    fix_table: bool = typer.Option(
        True,
        help="Whether to fix tables with png. Defaults to True.",
    ),
    debug: bool = typer.Option(
        False,
        help="Enable debug mode. Defaults to False.",
    ),
):
    """Convert LaTeX to Word with the given options."""
    locale_value: Optional[str] = None
    if caption_locale is not None:
        locale_value = caption_locale.strip()
        if not locale_value:
            locale_value = None

    author_metadata = _collect_author_metadata(
        authors or [],
        author_metadata_file,
    )

    converter = LatexToWordConverter(
        input_texfile,
        output_docxfile,
        reference_docfile=reference_docfile,
        bibfile=bibfile,
        cslfile=cslfile,
        fix_table=fix_table,
        debug=debug,
        caption_locale=locale_value,
        author_metadata=author_metadata,
    )

    try:
        converter.convert()
    except Tex2DocxError as exc:
        typer.secho(
            f"Conversion failed: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # pragma: no cover
        typer.secho(
            "Unexpected error during conversion. Enable --debug for details.",
            fg=typer.colors.RED,
            err=True,
        )
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


# Subcommand for downloading dependencies #TODO(Hua)
@app.command("init")
def download():
    """Download dependencies for the tex2docx tool."""

    # Check pandoc and pandoc-crossref
    if not shutil.which("pandoc"):
        typer.echo("Pandoc is not installed. Please install Pandoc first.")
        raise typer.Exit(code=1)
    if not shutil.which("pandoc-crossref"):
        typer.echo(
            "Pandoc-crossref is not installed. Please install "
            "Pandoc-crossref first."
        )
        raise typer.Exit(code=1)

    typer.echo("Downloading dependencies...")
    # Add code to download and install dependencies here
    # For example, you could call external package managers, etc.
    # Example placeholder:
    typer.echo("Dependencies installed successfully.")


if __name__ == "__main__":
    app()
