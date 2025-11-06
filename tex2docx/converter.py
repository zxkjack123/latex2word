"""Pandoc conversion functionality."""

import shutil
import subprocess
from typing import List, Optional

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
        luafile = self.config.luafile

        if output_texfile is None:
            raise FileNotFoundError("Modified TeX file path not configured.")
        if reference_docfile is None:
            raise FileNotFoundError("Reference document path not configured.")
        if luafile is None:
            raise FileNotFoundError("Lua filter path not configured.")

        if not output_texfile.exists():
            raise FileNotFoundError(
                f"Modified TeX file not found: {output_texfile}"
            )

        if not reference_docfile.exists():
            raise FileNotFoundError(
                f"Reference document not found: {reference_docfile}"
            )

        if not luafile.exists():
            raise FileNotFoundError(f"Lua filter not found: {luafile}")
    
    def _build_pandoc_command(self) -> List[str]:
        """
        Build the Pandoc command line.
        
        Returns:
            List of command arguments.
        """
        output_texfile = self.config.output_texfile
        output_docxfile = self.config.output_docxfile
        luafile = self.config.luafile
        reference_docfile = self.config.reference_docfile

        if luafile is None:
            raise FileNotFoundError("Lua filter path not configured.")
        if reference_docfile is None:
            raise FileNotFoundError("Reference document path not configured.")

        command = [
            "pandoc",
            str(output_texfile.name),  # Input file (relative to CWD)
            "-o",
            str(output_docxfile.name),  # Output file
        ]
        
        # Add Lua filter
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
        bibfile = self.config.bibfile
        return (
            bibfile is not None and
            bibfile.exists() and
            bibfile.is_file()
        )
    
    def _get_citation_options(self) -> List[str]:
        """
        Get citation-related command line options.
        
        Returns:
            List of citation options.
        """
        bibfile = self.config.bibfile
        cslfile = self.config.cslfile

        if bibfile is None:
            raise FileNotFoundError("Bibliography file not configured.")
        if cslfile is None:
            raise FileNotFoundError("CSL file not configured.")

        if not cslfile.exists() or not cslfile.is_file():
            raise FileNotFoundError(f"CSL file not found: {cslfile}")
        
        return PandocOptions.CITATION_OPTIONS + [
            "--bibliography",
            str(bibfile.resolve()),
            "--csl",
            str(cslfile.resolve()),
        ]
    
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
                errors="replace"
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
