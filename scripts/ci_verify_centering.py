"""CI smoke test: convert a minimal LaTeX file and assert centering.

This script:
- Creates a temporary working directory
- Writes a 1x1 PNG and a small LaTeX with one figure and one table
- Runs tex2docx conversion
- Parses the generated DOCX to assert:
  * all tables are centered
  * all paragraphs containing drawings (figures) are centered
Exits 1 on failure; prints diagnostics to stdout.
"""
from __future__ import annotations

import base64
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from tex2docx import LatexToWordConverter

_MINIMAL_PNG: str = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42"
    "mP8Xw8AAn0B9nLtV9kAAAAASUVORK5CYII="
)

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_W_VAL = f"{_W_NS}val"


def _write_dummy_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(_MINIMAL_PNG))


def _write_smoke_tex(path: Path, image_name: str) -> None:
    content = rf"""
    \documentclass{{article}}
    \usepackage{{graphicx}}
    \begin{{document}}

    % Inline image (no figure environment) to avoid LaTeX subfile compile
    \begin{{center}}
        \includegraphics{{{image_name}}}
    \end{{center}}

    \begin{{table}}
        \centering
        \caption{{Smoke table}}
        \begin{{tabular}}{{cc}}
        A & B \\\\
        1 & 2 \\\\
        \end{{tabular}}
    \end{{table}}

    \end{{document}}
    """
    path.write_text(
        "\n".join(line.strip() for line in content.splitlines()),
        encoding="utf-8",
    )


def _load_document_root(docx_path: Path) -> ET.Element:
    with zipfile.ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")
    return ET.fromstring(xml_bytes)


def _all_tables_centered(root: ET.Element) -> tuple[bool, int]:
    count = 0
    for tbl in root.iter(f"{_W_NS}tbl"):
        count += 1
        jc = tbl.find(f"{_W_NS}tblPr/{_W_NS}jc")
        if jc is None or jc.attrib.get(_W_VAL) != "center":
            return False, count
    return True, count


def _all_drawing_paragraphs_centered(root: ET.Element) -> tuple[bool, int]:
    checked = 0
    for p in root.iter(f"{_W_NS}p"):
        if p.find(f".//{_W_NS}drawing") is None:
            continue
        checked += 1
        jc = p.find(f"{_W_NS}pPr/{_W_NS}jc")
        if jc is None or jc.attrib.get(_W_VAL) != "center":
            return False, checked
    return True, checked


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    reference_doc = repo_root / "my_temp.docx"

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        img = tdir / "smoke.png"
        tex = tdir / "main.tex"
        out = tdir / "out.docx"

        _write_dummy_png(img)
        _write_smoke_tex(tex, image_name=img.name)

        conv = LatexToWordConverter(
            input_texfile=tex,
            output_docxfile=out,
            reference_docfile=(
                reference_doc if reference_doc.exists() else None
            ),
            debug=True,
        )
        conv.convert()

        if not out.exists() or out.stat().st_size == 0:
            print("[ERROR] DOCX not produced or empty:", out)
            return 1

        root = _load_document_root(out)
        t_ok, t_count = _all_tables_centered(root)
        d_ok, d_count = _all_drawing_paragraphs_centered(root)

        if t_count == 0:
            print("[ERROR] No tables found in DOCX; smoke doc malformed")
            return 1
        if d_count == 0:
            print(
                "[ERROR] No figure paragraphs found in DOCX; "
                "smoke doc malformed"
            )
            return 1

        if not t_ok:
            print("[ERROR] Not all tables are centered")
            return 1
        if not d_ok:
            print("[ERROR] Not all figure paragraphs are centered")
            return 1

        print("[OK] Centering verified:", {
            "tables": t_count,
            "figure_paragraphs": d_count,
        })
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
