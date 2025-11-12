"""LaTeX content parsing and preprocessing."""

import regex
from pathlib import Path
from typing import List, Optional, Set

from .config import ConversionConfig, YamlValue
from .constants import TexPatterns
from .exceptions import ParseError
from .utils import PatternMatcher, TextProcessor
from .authors import parse_author_metadata


class LatexParser:
    """Handles LaTeX content parsing and preprocessing."""
    
    def __init__(self, config: ConversionConfig) -> None:
        """
        Initialize the LaTeX parser.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.logger = config.setup_logger()
        self.input_file = Path(self.config.input_texfile)
        
        # Content state
        self.raw_content: Optional[str] = None
        self.clean_content: Optional[str] = None
        self.figure_contents: List[str] = []
        self.table_contents: List[str] = []
        self.graphicspath: Optional[Path] = None
        self.graphicspaths: List[Path] = []
        self.graphicspath_entries: List[str] = []
        self.include_directories: List[Path] = []
        self.figure_package: Optional[str] = None
        self.contains_chinese: bool = False
        self.author_metadata: Optional[YamlValue] = None
    
    def read_and_preprocess(self) -> None:
        """Read the main TeX file and handle includes and comments."""
        try:
            with open(
                self.input_file,
                "r",
                encoding="utf-8",
            ) as file:
                self.raw_content = file.read()
            self.logger.info("Read %s", self.input_file.name)
        except Exception as e:
            self.logger.error(
                "Error reading input file %s: %s",
                self.input_file,
                e,
            )
            raise ParseError(f"Could not read input file: {e}")
        
        # Remove comments first
        clean_content = TextProcessor.remove_comments(self.raw_content)
        self.logger.debug("Removed comments from main file")
        
        # Process includes iteratively
        clean_content = self._process_includes(clean_content)
        
        self.clean_content = clean_content
        self.logger.debug("Finished processing includes and comments")
    
    def _process_includes(self, content: str) -> str:
        """
        Process \\include directives iteratively to support nested includes.
        
        Args:
            content: The LaTeX content to process.
            
        Returns:
            Content with includes resolved.
        """
        while True:
            includes_found = regex.findall(TexPatterns.INCLUDE, content)
            if not includes_found:
                break  # No more includes found
            
            made_replacement = False
            processed_in_pass: Set[str] = set()
            
            for include_name in includes_found:
                include_directive = f"\\include{{{include_name}}}"
                
                # Skip if already processed in this pass
                if include_directive in processed_in_pass:
                    continue
                
                include_filename = self._get_include_filename(include_name)
                include_file_path = self.input_file.parent / include_filename
                
                if include_file_path.exists():
                    include_content = self._read_include_file(
                        include_file_path
                    )
                    if include_content is not None:
                        content = content.replace(
                            include_directive,
                            include_content,
                            1,
                        )
                        self.logger.debug(
                            "Included content from %s",
                            include_filename,
                        )
                        made_replacement = True
                        processed_in_pass.add(include_directive)
                        self._register_include_directory(
                            include_file_path.parent
                        )
                else:
                    self.logger.warning(
                        "Include file not found: %s",
                        include_file_path,
                    )
                    content = content.replace(
                        include_directive,
                        f"% Include file not found: {include_filename} %",
                        1,
                    )
                    processed_in_pass.add(include_directive)
            
            if not made_replacement:
                break  # Exit if no replacements were made
        
        return content
    
    @staticmethod
    def _get_include_filename(include_name: str) -> str:
        """Get the full filename for an include directive."""
        if not include_name.lower().endswith(".tex"):
            return f"{include_name}.tex"
        return include_name
    
    def _read_include_file(self, file_path: Path) -> Optional[str]:
        """
        Read and process an include file.
        
        Args:
            file_path: Path to the include file.
            
        Returns:
            Processed content or None if reading failed.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                include_content = file.read()
            # Remove comments from included file before inserting
            return TextProcessor.remove_comments(include_content)
        except Exception as e:
            self.logger.warning(
                "Could not read include file %s: %s",
                file_path,
                e,
            )
            return f"% Error including {file_path.name} %"
    
    def analyze_structure(self) -> None:
        """Analyze the cleaned content for figures, tables, packages, etc."""
        if not self.clean_content:
            raise ParseError("Clean content is not available for analysis")
        
        # Extract figures and tables
        figure_matches = PatternMatcher.match_pattern(
            TexPatterns.FIGURE, self.clean_content, mode="all"
        )
        if isinstance(figure_matches, list):
            self.figure_contents = figure_matches
        else:
            self.figure_contents = []
        
        table_matches = PatternMatcher.match_pattern(
            TexPatterns.TABLE, self.clean_content, mode="all"
        )
        if isinstance(table_matches, list):
            self.table_contents = table_matches
        else:
            self.table_contents = []
        
        self.logger.info(
            "Found %d figure environments",
            len(self.figure_contents),
        )
        self.logger.info(
            "Found %d table environments",
            len(self.table_contents),
        )
        
        # Determine figure package
        self.figure_package = PatternMatcher.find_figure_package(
            self.clean_content
        )
        self.logger.debug("Detected figure package: %s", self.figure_package)
        
        # Determine graphics path
        self._determine_graphicspath()
        
        # Check for Chinese characters
        combined_content = "".join(self.figure_contents + self.table_contents)
        self.contains_chinese = PatternMatcher.has_chinese_characters(
            combined_content
        )
        if self.contains_chinese:
            self.logger.debug("Detected Chinese characters in figures/tables")

        self._extract_author_metadata()
        self._detect_bibliography_file()
    
    def _determine_graphicspath(self) -> None:
        """Determine the graphics path from the LaTeX content."""
        base_directory = self.input_file.parent.resolve()
        if self.clean_content:
            entries = PatternMatcher.extract_graphicspaths(self.clean_content)
            self.graphicspath_entries = entries
            bases = [base_directory] + self.include_directories
            resolved_paths = self._resolve_graphicspath_entries(entries, bases)
        else:
            entries = []
            resolved_paths = []

        if not resolved_paths:
            resolved_paths = [base_directory]

        self.graphicspaths = resolved_paths
        if resolved_paths:
            self.graphicspath = resolved_paths[0]
        else:
            self.graphicspath = base_directory
        
        self.logger.debug("Determined graphics paths: %s", self.graphicspaths)
    
    def get_analysis_summary(self) -> dict:
        """
        Get a summary of the parsed content analysis.
        
        Returns:
            Dictionary containing analysis results.
        """
        return {
            "num_figures": len(self.figure_contents),
            "num_tables": len(self.table_contents),
            "figure_package": self.figure_package,
            "contains_chinese": self.contains_chinese,
            "graphicspath": (
                str(self.graphicspath) if self.graphicspath else None
            ),
            "graphicspaths": [str(path) for path in self.graphicspaths],
            "graphicspath_entries": list(self.graphicspath_entries),
            "include_directories": [
                str(path) for path in self.include_directories
            ],
            "has_clean_content": self.clean_content is not None,
            "has_author_metadata": self.author_metadata is not None,
        }

    def _extract_author_metadata(self) -> None:
        """Extract structured author metadata from the LaTeX content."""

        if not self.clean_content:
            return

        metadata = parse_author_metadata(self.clean_content)
        if metadata:
            self.author_metadata = metadata
            author_count = 0
            if isinstance(metadata, dict):
                authors_value = metadata.get("author")
                if isinstance(authors_value, list):
                    author_count = len(authors_value)
                elif authors_value is not None:
                    author_count = 1
            elif isinstance(metadata, list):
                author_count = len(metadata)
            else:
                author_count = 1
            self.logger.debug(
                "Extracted %d author entries from LaTeX metadata",
                author_count,
            )

    def _register_include_directory(self, directory: Path) -> None:
        """Track directories of included files for asset resolution."""
        resolved = directory.resolve()
        if resolved not in self.include_directories:
            self.include_directories.append(resolved)

    def _detect_bibliography_file(self) -> None:
        """Attempt to resolve bibliography files declared in LaTeX."""

        if not self.clean_content:
            return

        candidates = PatternMatcher.extract_bibliography_files(
            self.clean_content
        )
        if not candidates:
            return

        search_dirs = [self.input_file.parent] + self.include_directories
        seen: set[Path] = set()
        detected_any = False

        for raw_candidate in candidates:
            expanded = self._expand_bibliography_candidate(
                raw_candidate,
                search_dirs,
            )
            for path in expanded:
                if path in seen:
                    continue
                seen.add(path)
                if path.exists() and path.is_file():
                    self.config.add_bibliography_file(path)
                    self.logger.debug(
                        "Detected bibliography file: %s",
                        path,
                    )
                    detected_any = True

        if not detected_any:
            self.logger.debug(
                "No bibliography file resolved from LaTeX commands"
            )

    def _expand_bibliography_candidate(
        self,
        raw_candidate: str,
        base_directories: List[Path],
    ) -> List[Path]:
        """Expand bibliography hints into candidate file paths."""

        candidate = Path(raw_candidate).expanduser()
        targets: List[Path] = []

        if candidate.is_absolute():
            targets.append(candidate)
        else:
            for base in base_directories:
                targets.append((base / candidate).resolve())

        expanded: List[Path] = []
        for target in targets:
            expanded.append(target)
            if target.suffix.lower() != ".bib":
                expanded.append(target.with_suffix(".bib"))

        return expanded

    def _resolve_graphicspath_entries(
        self,
        entries: List[str],
        base_directories: List[Path],
    ) -> List[Path]:
        """Resolve graphicspath entries relative to the base document."""
        resolved: List[Path] = []
        seen: set[Path] = set()

        for entry in entries:
            candidate = Path(entry)
            if candidate.is_absolute():
                resolved_path = candidate.resolve()
                if resolved_path not in seen:
                    resolved.append(resolved_path)
                    seen.add(resolved_path)
                continue
            for base in base_directories:
                combined = (base / candidate).resolve()
                if combined not in seen:
                    resolved.append(combined)
                    seen.add(combined)

        return resolved
