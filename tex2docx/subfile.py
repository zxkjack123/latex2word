"""LaTeX subfile generation and compilation."""

import concurrent.futures
import multiprocessing as mp
import sys
import os
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from tqdm import tqdm

from .config import ConversionConfig
from .constants import TexTemplates, CompilerOptions
from .exceptions import ConfigurationError, FileNotFoundError
from .utils import PatternMatcher, TextProcessor


class SubfileGenerator:
    """Handles generation of LaTeX subfiles for figures and tables."""
    
    def __init__(self, config: ConversionConfig, parser_results: dict) -> None:
        """
        Initialize the subfile generator.
        
        Args:
            config: Configuration object.
            parser_results: Results from LaTeX parsing.
        """
        self.config = config
        self.logger = config.setup_logger()
        self.parser_results = parser_results
        
        # Storage for created files
        self.created_figure_files: Dict[int, str] = {}
        self.created_table_files: Dict[int, str] = {}
        self._asset_search_roots = self._build_asset_search_roots()
    
    def generate_figure_subfiles(self, figure_contents: List[str]) -> None:
        """
        Generate subfiles for figure environments.
        
        Args:
            figure_contents: List of figure environment strings.
        """
        self._validate_graphic_assets(figure_contents, "figure")
        self._generate_subfiles(
            figure_contents,
            "multifig",
            self.created_figure_files,
        )
    
    def generate_table_subfiles(self, table_contents: List[str]) -> None:
        """
        Generate subfiles for table environments.
        
        Args:
            table_contents: List of table environment strings.
        """
        self._validate_graphic_assets(table_contents, "table")
        self._generate_subfiles(
            table_contents,
            "tab",
            self.created_table_files,
        )
    
    def _generate_subfiles(
        self,
        content_list: List[str],
        prefix: str,
        storage_dict: Dict[int, str]
    ) -> None:
        """
        Generate subfiles for a list of LaTeX environments.
        
        Args:
            content_list: List of environment content strings.
            prefix: Filename prefix.
            storage_dict: Dictionary to store created filenames.
        """
        if not content_list:
            self.logger.info(f"No {prefix} environments to process")
            return
        
        default_counter = 0
        created_filenames = set(storage_dict.values())
        
        for index, item_content in enumerate(content_list):
            filename = self._generate_filename(
                item_content, prefix, default_counter, created_filenames
            )
            
            storage_dict[index] = filename
            created_filenames.add(filename)
            default_counter += 1
            
            graphicspath_entries = self._graphicspath_entries_for_content(
                item_content
            )
            self._write_subfile(item_content, filename, graphicspath_entries)
    
    def _generate_filename(
        self,
        content: str,
        prefix: str,
        counter: int,
        existing_names: set
    ) -> str:
        """
        Generate a unique filename for a subfile.
        
        Args:
            content: The LaTeX content.
            prefix: Filename prefix.
            counter: Default counter for fallback naming.
            existing_names: Set of already used filenames.
            
        Returns:
            A unique filename.
        """
        # Extract label for filename
        labels = PatternMatcher.match_pattern(
            r"\\label\{(.*?)\}", content, mode="all"
        )
        
        if labels:
            base_name = labels[-1]
            # Clean common prefixes
            for pfx in [
                "fig:",
                "fig-",
                "fig_",
                "tab:",
                "tab-",
                "tab_",
                "tbl:",
                "tbl-",
                "tbl_",
            ]:
                if base_name.startswith(pfx):
                    base_name = base_name[len(pfx):]
                    break
        else:
            base_name = f"{prefix}{counter}"
        
        # Sanitize filename
        safe_name = TextProcessor.sanitize_filename(base_name)
        filename = f"{prefix}_{safe_name}.tex"
        
        # Ensure uniqueness
        original_stem = f"{prefix}_{safe_name}"
        while filename in existing_names:
            unique_suffix = f"_{uuid.uuid4().hex[:4]}"
            filename = f"{original_stem}{unique_suffix}.tex"
        
        return filename
    
    def _write_subfile(
        self,
        content: str,
        filename: str,
        graphicspath_entries: List[str],
    ) -> None:
        """
        Write a subfile to disk.
        
        Args:
            content: The LaTeX content.
            filename: The filename to write to.
            graphicspath_rel: Relative graphics path.
        """
        try:
            file_content = self._generate_file_content(content, graphicspath_entries)
            file_path = self._temp_directory() / filename
            
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(file_content)
            
            self.logger.info(f"Created subfile: {filename}")
        except Exception as e:
            self.logger.error(f"Error writing subfile {filename}: {e}")
            # Remove from storage if creation failed
            for index, stored_filename in list(self.created_figure_files.items()):
                if stored_filename == filename:
                    del self.created_figure_files[index]
            for index, stored_filename in list(self.created_table_files.items()):
                if stored_filename == filename:
                    del self.created_table_files[index]
    
    def _generate_file_content(
        self,
        content: str,
        graphicspath_entries: List[str],
    ) -> str:
        """
        Generate the complete LaTeX file content for a subfile.
        
        Args:
            content: The original environment content.
            graphicspath_rel: Relative graphics path.
            
        Returns:
            Complete LaTeX file content.
        """
        # Process content
        processed_content = TextProcessor.comment_out_captions(content)
        processed_content = TextProcessor.remove_continued_float(processed_content)
        
        # Start with base template
        file_content = TexTemplates.BASE_MULTIFIG_TEXFILE
        
        # Set figure package
        figure_package = self.parser_results.get("figure_package")
        if figure_package == "subfig":
            package_lines = "\\usepackage{caption}\n\\usepackage{subfig}"
        elif figure_package == "subfigure":
            package_lines = "\\usepackage{subfigure}"
        elif figure_package == "subcaption":
            package_lines = (
                "\\usepackage{caption}\n"
                "\\usepackage{subcaption}"
            )
        else:
            package_lines = ""
        
        if package_lines:
            file_content = file_content.replace(
                "% FIGURE_PACKAGE_PLACEHOLDER %", package_lines
            )
        else:
            file_content = file_content.replace(
                "% FIGURE_PACKAGE_PLACEHOLDER %\n",
                "",
            )
        
        # Set CJK package if needed
        if self.parser_results.get("contains_chinese", False):
            cjk_line = "\\usepackage{xeCJK}"
            file_content = file_content.replace(
                "% CJK_PACKAGE_PLACEHOLDER %",
                cjk_line,
            )
        else:
            file_content = file_content.replace(
                "% CJK_PACKAGE_PLACEHOLDER %\n",
                "",
            )
        
        # Set graphics path
        joined_paths = "}{".join(graphicspath_entries)
        file_content = file_content.replace(
            "{GRAPHICSPATH_PLACEHOLDER}", joined_paths
        )
        
        # Insert content
        file_content = file_content.replace(
            "{FIGURE_CONTENT_PLACEHOLDER}", processed_content
        )
        
        return file_content

    def _build_asset_search_roots(self) -> List[Path]:
        """Determine directories to search for figure assets."""
        roots: List[Path] = []
        resolved = self.parser_results.get("graphicspaths") or []
        for path_str in resolved:
            try:
                roots.append(Path(path_str).resolve())
            except Exception:
                self.logger.debug(
                    "Could not resolve graphicspath '%s'",
                    path_str,
                )

        raw_entries = self.parser_results.get("graphicspath_entries") or []
        include_dirs = [
            Path(p).resolve()
            for p in self.parser_results.get("include_directories", [])
        ]
        base_dirs = [self._input_directory(), *include_dirs]

        for entry in raw_entries:
            candidate = Path(entry)
            if candidate.is_absolute():
                roots.append(candidate.resolve())
                continue
            for base_dir in base_dirs:
                roots.append((base_dir / candidate).resolve())

        roots.extend(base_dirs)
        seen: set[Path] = set()
        unique_roots: List[Path] = []
        for root in roots:
            try:
                resolved = root if root.is_absolute() else root.resolve()
            except Exception:
                resolved = root
            if resolved not in seen:
                unique_roots.append(resolved)
                seen.add(resolved)
        return unique_roots

    def _validate_graphic_assets(
        self,
        content_list: List[str],
        context: str,
    ) -> None:
        """Ensure all includegraphics assets referenced in content exist."""
        if not content_list:
            return

        missing: List[str] = []
        for index, content in enumerate(content_list):
            image_paths = PatternMatcher.extract_includegraphics_paths(content)
            if not image_paths:
                continue
            local_roots = self._resolve_local_graphicspaths(content)
            search_roots = [*local_roots, *self._asset_search_roots]
            for image_path in image_paths:
                if not self._asset_exists(image_path, search_roots):
                    descriptor = f"{context} #{index + 1}: {image_path}"
                    missing.append(descriptor)

        if missing:
            details = "\n".join(f"  - {item}" for item in missing)
            message = (
                "Missing graphic assets detected before compilation:\n"
                f"{details}\n"
                "Ensure all referenced files exist in the graphics path."
            )
            raise FileNotFoundError(message)

    def _asset_exists(
        self,
        asset_path: str,
        search_roots: List[Path],
    ) -> bool:
        """Check whether a referenced graphic asset exists on disk."""
        normalized = asset_path.strip()
        if not normalized:
            return True

        latex_path = Path(normalized)
        bases: List[Path] = []
        if latex_path.is_absolute():
            bases.append(latex_path)
        else:
            for root in search_roots:
                bases.append(root / latex_path)

        if latex_path.suffix:
            candidates = bases
        else:
            candidates = []
            for base in bases:
                candidates.extend(
                    base.with_suffix(ext)
                    for ext in self._supported_image_extensions()
                )

        for candidate in candidates:
            if candidate.exists():
                return True
        return False

    @staticmethod
    def _supported_image_extensions() -> Tuple[str, ...]:
        """Return the set of image extensions LaTeX commonly resolves."""
        return (
            ".pdf",
            ".PDF",
            ".ai",
            ".AI",
            ".png",
            ".PNG",
            ".jpg",
            ".JPG",
            ".jpeg",
            ".JPEG",
            ".jp2",
            ".JP2",
            ".jpf",
            ".JPF",
            ".bmp",
            ".BMP",
            ".ps",
            ".PS",
            ".eps",
            ".EPS",
            ".mps",
            ".MPS",
        )

    def _graphicspath_entries_for_content(self, content: str) -> List[str]:
        """Compute graphicspath entries for a specific LaTeX environment."""
        local_roots = self._resolve_local_graphicspaths(content)
        combined_roots = [*local_roots, *self._asset_search_roots]
        return self._format_graphicspath_entries(combined_roots)

    def _format_graphicspath_entries(self, roots: List[Path]) -> List[str]:
        """Convert directory paths into LaTeX graphicspath entries."""
        temp_dir = self._temp_directory()
        entries: List[str] = []
        for root in roots:
            try:
                rel = Path(os.path.relpath(root, temp_dir))
                value = rel.as_posix()
            except ValueError:
                value = root.as_posix()
            if not value.endswith("/"):
                value = f"{value}/"
            if value not in entries:
                entries.append(value)
        return entries

    def _resolve_local_graphicspaths(self, content: str) -> List[Path]:
        """Resolve graphicspath commands defined inside an environment."""
        entries = PatternMatcher.extract_graphicspaths(content)
        if not entries:
            return []

        include_dirs = [
            Path(path).resolve()
            for path in self.parser_results.get("include_directories", [])
        ]
        base_dirs = [self._input_directory(), *include_dirs]
        resolved: List[Path] = []
        seen: set[Path] = set()
        for entry in entries:
            candidate = Path(entry)
            if candidate.is_absolute():
                path = candidate.resolve()
                if path not in seen:
                    resolved.append(path)
                    seen.add(path)
                continue
            for base_dir in base_dirs:
                path = (base_dir / candidate).resolve()
                if path not in seen:
                    resolved.append(path)
                    seen.add(path)
        return resolved

    def _input_directory(self) -> Path:
        """Return the directory containing the primary input TeX file."""
        return Path(self.config.input_texfile).resolve().parent

    def _temp_directory(self) -> Path:
        """Return the configured temporary directory for subfiles."""
        temp_dir = self.config.temp_subtexfile_dir
        if temp_dir is None:
            raise ConfigurationError("Temporary directory is not configured")
        return temp_dir


class SubfileCompiler:
    """Handles compilation of LaTeX subfiles to PNG images."""
    
    def __init__(self, config: ConversionConfig) -> None:
        """
        Initialize the compiler.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.logger = config.setup_logger()
    
    def compile_all_subfiles(
        self,
        figure_files: Dict[int, str],
        table_files: Dict[int, str],
    ) -> None:
        """
        Compile all subfiles to PNG images in parallel.
        
        Args:
            figure_files: Dictionary of figure subfiles.
            table_files: Dictionary of table subfiles.
        """
        all_files = list(figure_files.values())
        if self.config.fix_table:
            all_files.extend(list(table_files.values()))
        
        if not all_files:
            self.logger.info("No subfiles to compile")
            return
        
        temp_dir = self.config.temp_subtexfile_dir
        if temp_dir is None:
            raise ConfigurationError("Temporary directory is not configured")

        full_paths = [temp_dir / fname for fname in all_files]

        successful, failed = self._compile_parallel(full_paths)

        self.logger.info(
            "Compilation finished. Success: %d, Failed: %d",
            successful,
            len(failed),
        )
        if failed:
            self.logger.warning(
                "Failed compilations: %s",
                ", ".join(failed),
            )

    def _compile_parallel(
        self,
        file_paths: List[Path],
    ) -> Tuple[int, List[str]]:
        """Compile files in parallel using ProcessPoolExecutor."""
        successful_count = 0
        failed_files: List[str] = []

        max_workers = min(CompilerOptions.MAX_WORKERS, len(file_paths))

        context = self._select_executor_context()
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=max_workers,
            mp_context=context,
        ) as executor:
            futures = {
                executor.submit(self._compile_single_file, path): path
                for path in file_paths
            }

            progress = tqdm(
                concurrent.futures.as_completed(futures),
                total=len(futures),
                desc="Compiling subfiles",
                unit="file",
            )

            for future in progress:
                file_path = futures[future]
                try:
                    success = future.result()
                    if success:
                        successful_count += 1
                    else:
                        failed_files.append(file_path.name)
                except Exception as exc:
                    self.logger.error(
                        "Compilation exception for %s: %s",
                        file_path.name,
                        exc,
                    )
                    failed_files.append(file_path.name)

        return successful_count, failed_files

    def _select_executor_context(self) -> mp.context.BaseContext:
        """Choose an executor context that works in the current runtime."""

        main_path = Path(sys.argv[0]) if sys.argv else None
        spawn_supported = True

        if main_path is None or not main_path.exists():
            spawn_supported = False
        elif main_path.name == "<stdin>":
            spawn_supported = False

        if spawn_supported:
            try:
                return mp.get_context("spawn")
            except ValueError:
                self.logger.warning(
                    "Spawn context unavailable; falling back to default",
                )

        self.logger.debug(
            "Using default multiprocessing context for subfile compiler",
        )
        return mp.get_context()
    
    @staticmethod
    def _compile_single_file(file_path: Path) -> bool:
        """
        Compile a single TeX file to PNG.
        
        Args:
            file_path: Path to the TeX file.
            
        Returns:
            True if compilation succeeded, False otherwise.
        """
        command = [
            "xelatex",
            *CompilerOptions.XELATEX_OPTIONS,
            file_path.name,
        ]
        
        try:
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=file_path.parent,
                timeout=CompilerOptions.XELATEX_TIMEOUT,
            )
            
            # Write logs
            with open(
                file_path.with_suffix(".out"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(result.stdout)
            with open(
                file_path.with_suffix(".err"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(result.stderr)
            
            # Check for PNG file
            return SubfileCompiler._handle_png_output(file_path)
            
        except subprocess.CalledProcessError as exc:
            SubfileCompiler._log_compilation_failure(file_path, exc)
            return False
        except Exception:
            return False
    
    @staticmethod
    def _handle_png_output(tex_path: Path) -> bool:
        """
                    errors="replace",
                    timeout=CompilerOptions.XELATEX_TIMEOUT,
        
        Args:
            tex_path: Path to the source TeX file.
            
        Returns:
            True if PNG was successfully created/renamed, False otherwise.
        """
        expected_png = tex_path.with_suffix(".png")
        
        if expected_png.exists():
            return True
        
        # Look for PNGs with page numbers
        pattern = f"{tex_path.stem}*.png"
        created_pngs = list(tex_path.parent.glob(pattern))
        
        if not created_pngs:
            return False
        
        try:
            # Rename first PNG to expected name
            if expected_png.exists():
                expected_png.unlink()
            created_pngs[0].rename(expected_png)
            return True
        except Exception:
            return False
    
    @staticmethod
    def _log_compilation_failure(
        file_path: Path,
        error: subprocess.CalledProcessError,
    ) -> None:
        """
        Log compilation failure details.
        
        Args:
            file_path: Path to the failed file.
            error: The subprocess error.
        """
        try:
            with open(
                file_path.with_suffix(".out"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(error.stdout or "")
            with open(
                file_path.with_suffix(".err"),
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(error.stderr or "")
        except Exception:
            pass  # Ignore logging failures
