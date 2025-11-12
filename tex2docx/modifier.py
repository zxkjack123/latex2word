"""LaTeX content modification and reference updating."""

import regex
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import ConversionConfig
from .constants import TexPatterns, TexTemplates
from .utils import PatternMatcher, TextProcessor


class ContentModifier:
    """Handles modification of LaTeX content and reference updates."""
    
    def __init__(self, config: ConversionConfig) -> None:
        """
        Initialize the content modifier.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self.logger = config.setup_logger()
        self.modified_content: Optional[str] = None
    
    def create_modified_content(
        self,
        clean_content: str,
        figure_contents: List[str],
        table_contents: List[str],
        figure_files: Dict[int, str],
        table_files: Dict[int, str]
    ) -> str:
        """
        Create the modified LaTeX content with replaced environments.
        
        Args:
            clean_content: The clean LaTeX content.
            figure_contents: List of figure environment strings.
            table_contents: List of table environment strings.
            figure_files: Dictionary mapping indices to figure filenames.
            table_files: Dictionary mapping indices to table filenames.
            
        Returns:
            Modified LaTeX content.
        """
        self.modified_content = clean_content
        
        # Replace figure environments
        self._replace_environments(
            figure_contents,
            figure_files,
            self.config.get_multifig_template(),
            "fig"
        )
        
        # Replace table environments if enabled
        if self.config.fix_table:
            self._replace_environments(
                table_contents,
                table_files,
                TexTemplates.MODIFIED_TABENV,
                "tbl"
            )
        
        # Update graphics path
        self._update_graphicspath()

        # Normalize table label prefixes for consistency with pandoc-crossref
        self._normalize_table_labels()

        # Unwrap resizebox wrappers so Pandoc can recognize tables.
        self._unwrap_resizebox_tabular()

        # Ensure table rule commands are compatible with Pandoc output
        self._normalize_table_rules()

        # Fix any broken \ref commands that may have been split across lines
        self._fix_broken_refs()
        
        return self.modified_content
    
    def write_modified_file(self) -> None:
        """Write the modified content to the output TeX file."""
        if not self.modified_content:
            raise ValueError("No modified content to write")
        
        try:
            with open(self.config.output_texfile, "w", encoding="utf-8") as f:
                f.write(self.modified_content)
            self.logger.info(f"Created modified TeX file: {self.config.output_texfile.name}")
        except Exception as e:
            self.logger.error(f"Error writing modified TeX file: {e}")
            raise
    
    def _replace_environments(
        self,
        original_contents: List[str],
        created_files: Dict[int, str],
        template: str,
        label_prefix: str
    ) -> None:
        """
        Replace original environments with image includes.
        
        Args:
            original_contents: List of original environment strings.
            created_files: Dictionary mapping indices to filenames.
            template: LaTeX template for new environment.
            label_prefix: Prefix for new labels.
        """
        processed_indices = set()
        
        for index, original_content in enumerate(original_contents):
            if index in processed_indices or index not in created_files:
                continue
            
            # Generate new environment
            new_env = self._create_new_environment(
                original_content, created_files[index], template, label_prefix, index
            )
            
            if new_env and original_content in self.modified_content:
                # Replace content
                self.modified_content = self.modified_content.replace(
                    original_content, new_env, 1
                )
                processed_indices.add(index)
                
                # Update references
                self._update_references(original_content, new_env)
            else:
                self.logger.warning(
                    f"Could not replace environment {index} ({label_prefix})"
                )
    
    def _create_new_environment(
        self,
        original_content: str,
        filename: str,
        template: str,
        label_prefix: str,
        index: int
    ) -> Optional[str]:
        """
        Create a new environment replacing the original.
        
        Args:
            original_content: Original environment content.
            filename: PNG filename to include.
            template: LaTeX template to use.
            label_prefix: Prefix for the new label.
            index: Environment index.
            
        Returns:
            New environment string or None if creation failed.
        """
        # Extract caption
        caption = PatternMatcher.match_pattern(
            TexPatterns.CAPTION, original_content, mode="last"
        ) or ""
        
        # Generate new label
        base_name = Path(filename).stem
        safe_label = TextProcessor.sanitize_filename(base_name)
        new_label = f"{label_prefix}:{safe_label}"
        
        # PNG filename (just the name, not the path)
        png_filename = f"{base_name}.png"
        
        self.logger.debug(
            f"Creating new environment {index} ({label_prefix}):\n"
            f"  Caption: {caption[:50]}...\n"
            f"  Label: {new_label}\n"
            f"  PNG: {png_filename}"
        )
        
        # Format template based on its structure
        if template == TexTemplates.MULTIFIG_FIGENV:
            # Template order: image_path, caption, label
            return template % (png_filename, caption, new_label)
        elif template == TexTemplates.MODIFIED_TABENV:
            # Template order: caption, label, image_path
            return template % (caption, new_label, png_filename)
        else:
            self.logger.error(f"Unknown template for {label_prefix}")
            return None
    
    def _update_references(self, original_content: str, new_env: str) -> None:
        """
        Update references in the modified content.
        
        Args:
            original_content: Original environment content.
            new_env: New environment content.
        """
        # Extract the new label from the new environment
        new_label_match = regex.search(TexPatterns.LABEL, new_env)
        if not new_label_match:
            return
        
        new_label = new_label_match.group(1)
        
        # Update subfigure references
        self._update_subfigure_references(original_content, new_label)
        
        # Update main figure/table reference
        self._update_main_reference(original_content, new_label)
    
    def _update_subfigure_references(self, original_content: str, new_label: str) -> None:
        """
        Update references to subfigures.
        
        Args:
            original_content: Original environment content.
            new_label: New base label for the environment.
        """
        # Find includegraphics commands and their associated labels
        label_matches = regex.findall(TexPatterns.LABEL, original_content)
        main_label = label_matches[-1] if label_matches else None

        includegraphics_matches = list(
            regex.finditer(TexPatterns.INCLUDEGRAPHICS, original_content)
        )
        
        for i, img_match in enumerate(includegraphics_matches):
            # Look for the next label after this includegraphics
            start_pos = img_match.end()
            end_pos = (
                includegraphics_matches[i + 1].start()
                if i + 1 < len(includegraphics_matches)
                else len(original_content)
            )
            
            search_area = original_content[start_pos:end_pos]
            label_match = regex.search(TexPatterns.LABEL, search_area)
            
            if label_match:
                subfig_label = label_match.group(1)
                if subfig_label == main_label:
                    continue

                subfig_char = chr(ord('a') + i)

                old_ref = f"\\ref{{{subfig_label}}}"
                new_ref = f"\\ref{{{new_label}}}({subfig_char})"

                if old_ref in self.modified_content:
                    self.modified_content = self.modified_content.replace(
                        old_ref,
                        new_ref,
                    )
                    self.logger.debug(
                        "Updated subfigure reference '%s' -> '%s(%s)'",
                        subfig_label,
                        new_label,
                        subfig_char,
                    )
    
    def _update_main_reference(self, original_content: str, new_label: str) -> None:
        """
        Update the main figure/table reference.
        
        Args:
            original_content: Original environment content.
            new_label: New label for the environment.
        """
        label_matches = list(regex.finditer(TexPatterns.LABEL, original_content))
        if label_matches:
            main_label = label_matches[-1].group(1)

            old_ref = f"\\ref{{{main_label}}}"
            new_ref = f"\\ref{{{new_label}}}"

            if old_ref in self.modified_content:
                self.modified_content = self.modified_content.replace(
                    old_ref,
                    new_ref,
                )
                self.logger.debug(
                    "Updated main reference '%s' -> '%s'",
                    main_label,
                    new_label,
                )

    def _normalize_table_labels(self) -> None:
        """Convert legacy tab: prefixes to tbl: for labels and references."""
        if not self.modified_content:
            return

        def replace_label(match: regex.Match) -> str:
            return f"\\label{{tbl:{match.group(1)}}}"

        def replace_ref(match: regex.Match) -> str:
            return f"\\ref{{tbl:{match.group(1)}}}"

        self.modified_content = regex.sub(
            r"\\label\{tab:([^}]+)\}",
            replace_label,
            self.modified_content,
        )

        self.modified_content = regex.sub(
            r"\\ref\{tab:([^}]+)\}",
            replace_ref,
            self.modified_content,
        )

    def _normalize_table_rules(self) -> None:
        """Normalize table rule commands and add three-line defaults."""
        if not self.modified_content:
            return

        pattern = regex.compile(
            r"\\begin\{(?P<env>tabular\*?|tabularx|longtable)\}"
            r"(?P<options>(?:\[[^\]]*\])?(?:\{[^{}]*\})*)"
            r"(?P<body>.*?)"
            r"\\end\{(?P=env)\}",
            regex.DOTALL,
        )

        def replace_table(match: regex.Match) -> str:
            env = match.group("env")
            options = match.group("options") or ""
            body = match.group("body")

            transformed = self._convert_booktabs_rules(body)

            if not regex.search(r"\\(hline|cline)", transformed):
                transformed = self._apply_three_line_table_default(transformed)

            return f"\\begin{{{env}}}{options}{transformed}\\end{{{env}}}"

        self.modified_content = pattern.sub(replace_table, self.modified_content)

    @staticmethod
    def _convert_booktabs_rules(body: str) -> str:
        """Convert booktabs rule macros to standard \hline commands."""
        replacements = [
            (r"\\toprule(?:\[[^\]]*\])?", r"\\hline"),
            (r"\\midrule(?:\[[^\]]*\])?", r"\\hline"),
            (r"\\bottomrule(?:\[[^\]]*\])?", r"\\hline"),
            (r"\\cmidrule(?:\[[^\]]*\])?\{[^}]+\}", r"\\hline"),
        ]

        result = body
        for pattern, replacement in replacements:
            result = regex.sub(pattern, replacement, result)

        # Remove spacing directives that have no docx equivalent.
        result = regex.sub(r"\\addlinespace(?:\[[^\]]*\])?", "", result)

        return result

    def _unwrap_resizebox_tabular(self) -> None:
        """Remove resizebox wrappers around tabular environments."""
        if not self.modified_content:
            return

        content = self.modified_content
        replacements: List[Tuple[int, int, str]] = []
        pattern = regex.compile(r"\\resizebox\s*\{")
        search_pos = 0

        while True:
            match = pattern.search(content, search_pos)
            if not match:
                break

            start_index = match.start()
            brace_start = content.find("{", match.end() - 1)
            if brace_start == -1:
                break

            _, next_index = self._extract_braced_segment(content, brace_start)
            next_index = self._skip_whitespace(content, next_index)
            if next_index >= len(content) or content[next_index] != "{":
                search_pos = match.end()
                continue

            _, next_index = self._extract_braced_segment(content, next_index)
            next_index = self._skip_whitespace(content, next_index)
            if next_index >= len(content) or content[next_index] != "{":
                search_pos = match.end()
                continue

            body, body_end = self._extract_braced_segment(content, next_index)
            if body.lstrip().startswith("\\begin{tabular"):
                replacements.append((start_index, body_end, body.strip()))

            search_pos = match.end()

        if not replacements:
            return

        new_content_parts: List[str] = []
        last_index = 0
        for start, end, body in replacements:
            new_content_parts.append(content[last_index:start])
            new_content_parts.append(body)
            last_index = end

        new_content_parts.append(content[last_index:])
        self.modified_content = "".join(new_content_parts)

        for _, _, body in replacements:
            self.logger.debug("Unwrapped resizebox around tabular: %s", body.splitlines()[0])

    @staticmethod
    def _extract_braced_segment(content: str, start_index: int) -> Tuple[str, int]:
        """Extract a balanced braced segment starting at start_index."""
        if start_index >= len(content) or content[start_index] != "{":
            raise ValueError("Expected opening brace when extracting segment")

        depth = 0
        end_index = start_index
        while end_index < len(content):
            char = content[end_index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    segment = content[start_index + 1 : end_index]
                    return segment, end_index + 1
            end_index += 1

        raise ValueError("Unbalanced braces in resizebox segment")

    @staticmethod
    def _skip_whitespace(content: str, index: int) -> int:
        """Advance index forward while whitespace is encountered."""
        while index < len(content) and content[index].isspace():
            index += 1
        return index

    def _apply_three_line_table_default(self, body: str) -> str:
        """Insert top, header, and bottom rules for unstyled tables."""
        lines = body.splitlines()
        if not lines:
            return body

        ends_with_newline = body.endswith("\n")
        first_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first_idx is None:
            return body

        indent_match = regex.match(r"\s*", lines[first_idx])
        indent = indent_match.group(0) if indent_match else ""

        header_idx = next(
            (i for i in range(first_idx, len(lines)) if "\\\\" in lines[i]),
            None,
        )

        lines.insert(first_idx, f"{indent}\\hline")

        if header_idx is not None:
            header_insert_idx = header_idx + 2
            lines.insert(header_insert_idx, f"{indent}\\hline")

        trailing_blank = []
        while lines and lines[-1].strip() == "":
            trailing_blank.insert(0, lines.pop())

        lines.append(f"{indent}\\hline")
        lines.extend(trailing_blank)

        self.logger.debug("Applied default three-line style to table without rules")

        result = "\n".join(lines)
        if ends_with_newline:
            result += "\n"
        return result
    
    def _update_graphicspath(self) -> None:
        """Update the graphics path in the modified content."""
        # Remove existing graphicspath
        self.modified_content = regex.sub(
            TexPatterns.GRAPHICSPATH, "", self.modified_content
        )
        
        # Add new graphicspath pointing to temp directory
        temp_dir_name = self.config.temp_subtexfile_dir.name
        new_graphicspath = f"\\graphicspath{{{{{temp_dir_name}/}}}}"
        
        # Try to insert after documentclass or usepackage
        insert_pattern = r"(\\documentclass.*?\}\s*)|(\\usepackage.*?\}\s*)"
        last_match_end = 0
        
        for match in regex.finditer(insert_pattern, self.modified_content, regex.DOTALL):
            last_match_end = match.end()
        
        if last_match_end > 0:
            # Insert after last match
            self.modified_content = (
                self.modified_content[:last_match_end] +
                new_graphicspath + "\n" +
                self.modified_content[last_match_end:]
            )
            self.logger.debug("Inserted graphicspath after preamble")
        else:
            # Fallback: insert at beginning
            self.modified_content = new_graphicspath + "\n" + self.modified_content
            self.logger.debug("Inserted graphicspath at beginning (fallback)")
        
        self.logger.debug(f"Set graphicspath to: {new_graphicspath}")
    
    def _fix_broken_refs(self) -> None:
        """Fix broken \\ref commands that may have been split across lines."""
        import regex
        
        # Pattern to match broken \ref commands
        # This matches backslash followed by newline or carriage return followed by "ef{"
        broken_ref_pattern = r"\\[\r\n]+ef\{"
        
        # Count occurrences before fixing
        broken_count = len(regex.findall(broken_ref_pattern, self.modified_content))
        
        if broken_count > 0:
            self.logger.debug(f"Found {broken_count} broken \\ref commands")
            
            # Fix the broken references
            self.modified_content = regex.sub(broken_ref_pattern, r"\\ref{", self.modified_content)
            
            self.logger.debug(f"Fixed {broken_count} broken \\ref commands")
        
        # Also fix any other common broken LaTeX commands that might occur
        # Pattern for \label commands
        broken_label_pattern = r"\\[\r\n]+label\{"
        broken_label_count = len(regex.findall(broken_label_pattern, self.modified_content))
        
        if broken_label_count > 0:
            self.logger.debug(f"Found {broken_label_count} broken \\label commands")
            self.modified_content = regex.sub(broken_label_pattern, r"\\label{", self.modified_content)
            self.logger.debug(f"Fixed {broken_label_count} broken \\label commands")
