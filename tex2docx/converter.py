"""Pandoc conversion functionality."""

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional
from xml.etree import ElementTree as ET

from .config import ConversionConfig
from .constants import PandocOptions
from .exceptions import ConversionError, DependencyError


class PandocConverter:
    """Handles conversion from LaTeX to DOCX using Pandoc."""
    
    def __init__(self, config: ConversionConfig) -> None:
        """
        Initialize the Pandoc converter.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.logger = config.setup_logger()
    
    def convert_to_docx(self) -> None:
        """Convert the modified TeX file to DOCX using Pandoc."""
        # Check dependencies
        self._check_dependencies()
        
        # Validate files
        self._validate_files()
        
        # Build and run command
        command = self._build_pandoc_command()
        self._run_pandoc(command)

        # Apply table styling adjustments to match three-line formatting
        self._apply_docx_table_styling()
    
    def _check_dependencies(self) -> None:
        """Check that required external dependencies are available."""
        pandoc_path = shutil.which("pandoc")
        if not pandoc_path:
            raise DependencyError(
                "pandoc not found in PATH. Please install pandoc: "
                "https://pandoc.org"
            )

        crossref_path = shutil.which("pandoc-crossref")
        if not crossref_path:
            # Fail fast if pandoc-crossref is missing since we rely on it
            # for consistent cross-references in the generated DOCX.
            raise DependencyError(
                "pandoc-crossref not found in PATH. Please install "
                "pandoc-crossref (e.g. https://github.com/lierdakil/"
                "pandoc-crossref)."
            )

        # Log resolved paths and tool versions for reproducibility
        self.logger.debug(f"Found pandoc at: {pandoc_path}")
        self.logger.debug(f"Found pandoc-crossref at: {crossref_path}")
        self._log_tool_versions()

    def _get_tool_version(self, tool: str) -> Optional[str]:
        """Return the first line of 'tool --version' output, or None on error.

        This isolates external calls and keeps logging consistent.
        """
        try:
            result = subprocess.run(
                [tool, "--version"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            out = result.stdout.strip() or result.stderr.strip()
            if out:
                # Return only the first line to keep logs concise
                return out.splitlines()[0].strip()
        except Exception:
            # Don't raise here; caller will decide what to do.
            return None
        return None

    def _log_tool_versions(self) -> None:
        """Detect and log versions of external tools used by the converter.

        Logged at INFO so that conversion output contains reproducibility
        information in normal runs. If detection fails, warn instead.
        """
        pandoc_ver = self._get_tool_version("pandoc")
        crossref_ver = self._get_tool_version("pandoc-crossref")

        if pandoc_ver:
            self.logger.info(f"Detected pandoc: {pandoc_ver}")
        else:
            self.logger.warning("Could not detect pandoc version")

        if crossref_ver:
            self.logger.info(f"Detected pandoc-crossref: {crossref_ver}")
        else:
            self.logger.warning("Could not detect pandoc-crossref version")
    
    def _validate_files(self) -> None:
        """Validate that required files exist."""
        output_texfile = self.config.output_texfile
        reference_docfile = self.config.reference_docfile
        lua_filters = self.config.get_lua_filters()

        if output_texfile is None:
            raise FileNotFoundError("Modified TeX file path not configured.")
        if reference_docfile is None:
            raise FileNotFoundError("Reference document path not configured.")
        if not lua_filters:
            raise FileNotFoundError("Lua filters not configured.")

        if not output_texfile.exists():
            raise FileNotFoundError(
                f"Modified TeX file not found: {output_texfile}"
            )

        if not reference_docfile.exists():
            raise FileNotFoundError(
                f"Reference document not found: {reference_docfile}"
            )

        missing_filters = [
            str(path)
            for path in lua_filters
            if not path.exists()
        ]
        if missing_filters:
            raise FileNotFoundError(
                "Lua filter not found: " + ", ".join(missing_filters)
            )
    
    def _build_pandoc_command(self) -> List[str]:
        """
        Build the Pandoc command line.
        
        Returns:
            List of command arguments.
        """
        output_texfile = self.config.output_texfile
        output_docxfile = self.config.output_docxfile
        lua_filters = self.config.get_lua_filters()
        reference_docfile = self.config.reference_docfile

        if not lua_filters:
            raise FileNotFoundError("Lua filters not configured.")
        if reference_docfile is None:
            raise FileNotFoundError("Reference document path not configured.")

        command = [
            "pandoc",
            str(output_texfile.name),  # Input file (relative to CWD)
            "-o",
            str(output_docxfile.name),  # Output file
        ]
        
        # Add Lua filters
        for luafile in lua_filters:
            command.extend([
                "--lua-filter",
                str(luafile.resolve()),
            ])
        
        # Add filters
        command.extend(PandocOptions.FILTER_OPTIONS)
        
        # Add reference document
        command.extend([
            "--reference-doc",
            str(reference_docfile.resolve()),
        ])

        metadata_file = self.config.get_metadata_file()
        if not metadata_file.exists():
            raise FileNotFoundError(
                f"Pandoc metadata file not found: {metadata_file}"
            )
        command.extend([
            "--metadata-file",
            str(metadata_file.resolve()),
        ])
        
        # Add basic options
        command.extend(PandocOptions.BASIC_OPTIONS)
        
        # Add citation options if bibliography is available
        if self._should_add_citations():
            command.extend(self._get_citation_options())
        
        return command
    
    def _should_add_citations(self) -> bool:
        """Check if citation processing should be enabled."""
        return self.config.has_bibliography()
    
    def _get_citation_options(self) -> List[str]:
        """
        Get citation-related command line options.
        
        Returns:
            List of citation options.
        """
        bibliography_files = self.config.get_bibliography_files()
        cslfile = self.config.cslfile

        if not bibliography_files:
            raise FileNotFoundError("Bibliography files not configured.")
        if cslfile is None:
            raise FileNotFoundError("CSL file not configured.")

        if not cslfile.exists() or not cslfile.is_file():
            raise FileNotFoundError(f"CSL file not found: {cslfile}")

        citation_args = list(PandocOptions.CITATION_OPTIONS)

        added = False
        for bibfile in bibliography_files:
            if bibfile.exists() and bibfile.is_file():
                citation_args.extend([
                    "--bibliography",
                    str(bibfile.resolve()),
                ])
                added = True

        if not added:
            raise FileNotFoundError("No valid bibliography files found.")

        citation_args.extend([
            "--csl",
            str(cslfile.resolve()),
        ])

        return citation_args
    
    def _run_pandoc(self, command: List[str]) -> None:
        """
        Execute the Pandoc command.
        
        Args:
            command: Command line arguments.
        """
        self.logger.debug(f"Pandoc command: {' '.join(command)}")
        
        output_texfile = self.config.output_texfile
        output_docxfile = self.config.output_docxfile

        if output_texfile is None:
            raise ConversionError("Modified TeX file path not configured.")

        # Execute in the directory containing the modified TeX file
        cwd = output_texfile.parent
        
        try:
            result = subprocess.run(
                command,
                check=True,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=PandocOptions.TIMEOUT,
            )
            
            self.logger.info(
                f"Successfully converted {output_texfile.name} to "
                f"{output_docxfile.name}"
            )
            
            # Log warnings if any
            if result.stderr:
                self.logger.warning(f"Pandoc stderr:\n{result.stderr}")
            if result.stdout:
                self.logger.debug(f"Pandoc stdout:\n{result.stdout}")
                
        except subprocess.TimeoutExpired as exc:
            timeout_seconds = PandocOptions.TIMEOUT
            self.logger.error(
                "Pandoc conversion exceeded timeout (%s seconds)",
                timeout_seconds,
            )
            if exc.stderr:
                self.logger.error(
                    "Pandoc stderr before timeout:\n%s",
                    exc.stderr,
                )
            if exc.stdout:
                self.logger.debug(
                    "Pandoc stdout before timeout:\n%s",
                    exc.stdout,
                )
            raise ConversionError(
                "Pandoc conversion timed out after "
                f"{timeout_seconds} seconds."
            ) from exc
        except subprocess.CalledProcessError as e:
            error_msg = (
                f"Pandoc conversion failed (return code: {e.returncode})\n"
                f"stdout: {e.stdout}\n"
                f"stderr: {e.stderr}"
            )
            self.logger.error(error_msg)
            raise ConversionError(f"Pandoc conversion failed: {e}")
        except Exception as e:
            self.logger.error(
                f"Unexpected error during Pandoc conversion: {e}"
            )
            raise ConversionError(f"Unexpected conversion error: {e}")

    def _apply_docx_table_styling(self) -> None:
        """Post-process the DOCX to enforce three-line table styling."""
        output_docxfile = self.config.output_docxfile
        if output_docxfile is None or not output_docxfile.exists():
            return

        try:
            with zipfile.ZipFile(output_docxfile, "r") as archive:
                try:
                    document_xml = archive.read("word/document.xml")
                except KeyError:
                    self.logger.warning(
                        "Missing word/document.xml in DOCX; skip table styling"
                    )
                    return
        except zipfile.BadZipFile:
            self.logger.warning(
                "Unable to open DOCX archive for styling adjustments"
            )
            return

        try:
            root = ET.fromstring(document_xml)
        except ET.ParseError as exc:
            self.logger.warning(
                "Failed to parse document.xml (%s); skipping table styling",
                exc,
            )
            return

        namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }

        modified = False
        for tbl in root.findall(".//w:tbl", namespaces):
            if self._style_docx_table(tbl, namespaces):
                modified = True

        if not modified:
            return

        updated_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            with zipfile.ZipFile(output_docxfile, "r") as src:
                src.extractall(temp_dir)

            document_path = temp_dir / "word" / "document.xml"
            document_path.write_bytes(updated_xml)

            temp_docx = temp_dir / "styled.docx"
            with zipfile.ZipFile(temp_docx, "w", zipfile.ZIP_DEFLATED) as dest:
                for item in sorted(temp_dir.rglob("*")):
                    if item == temp_docx:
                        continue
                    if item.is_file():
                        dest.write(item, item.relative_to(temp_dir))

            shutil.move(str(temp_docx), output_docxfile)
            self.logger.debug("Applied three-line styling to DOCX tables")

    @staticmethod
    def _style_docx_table(tbl: ET.Element, namespaces: dict) -> bool:
        """Ensure a table has top, header, and bottom rules."""
        ns = namespaces["w"]
        modified = False

        tbl_pr = tbl.find("w:tblPr", namespaces)
        if tbl_pr is None:
            tbl_pr = ET.SubElement(tbl, f"{{{ns}}}tblPr")

        tbl_borders = tbl_pr.find("w:tblBorders", namespaces)
        if tbl_borders is None:
            tbl_borders = ET.SubElement(tbl_pr, f"{{{ns}}}tblBorders")

        if PandocConverter._ensure_border(tbl_borders, namespaces, "top"):
            modified = True
        if PandocConverter._ensure_border(tbl_borders, namespaces, "bottom"):
            modified = True

        first_row = tbl.find("w:tr", namespaces)
        if first_row is not None:
            tr_pr = first_row.find("w:trPr", namespaces)
            if tr_pr is None:
                tr_pr = ET.SubElement(first_row, f"{{{ns}}}trPr")
            tr_borders = tr_pr.find("w:trBorders", namespaces)
            if tr_borders is None:
                tr_borders = ET.SubElement(tr_pr, f"{{{ns}}}trBorders")
            if PandocConverter._ensure_border(
                tr_borders, namespaces, "bottom"
            ):
                modified = True

        return modified

    @staticmethod
    def _ensure_border(
        parent: ET.Element,
        namespaces: dict,
        position: str,
    ) -> bool:
        """Create or update a DOCX border element."""
        ns = namespaces["w"]
        border = parent.find(f"w:{position}", namespaces)
        if border is None:
            border = ET.SubElement(parent, f"{{{ns}}}{position}")
            modified = True
        else:
            modified = False

        border.set(f"{{{ns}}}val", "single")
        border.set(f"{{{ns}}}sz", "12")
        border.set(f"{{{ns}}}space", "0")
        border.set(f"{{{ns}}}color", "auto")

        return modified
