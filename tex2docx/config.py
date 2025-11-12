"""Configuration management for tex2docx."""

from __future__ import annotations

import logging
import uuid
from collections import OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from .constants import PandocOptions, TexTemplates

YamlValue = Union[
    Dict[str, Any],
    List[Any],
    str,
    int,
    float,
    bool,
    None,
]


def _yaml_quote(value: str) -> str:
    """Return a YAML-safe quoted string."""
    escaped = value.replace("\\", "\\\\").replace("\"", "\\\"")
    escaped = escaped.replace("\n", "\\n")
    return f'"{escaped}"'


def _render_yaml(value: YamlValue, indent: int = 0) -> List[str]:
    """Render limited Python structures into YAML lines."""
    prefix = "  " * indent

    if isinstance(value, dict):
        lines: List[str] = []
        for key, item in value.items():
            if isinstance(item, dict) and item:
                lines.append(f"{prefix}{key}:")
                lines.extend(_render_yaml(item, indent + 1))
                continue
            if isinstance(item, list) and item:
                lines.append(f"{prefix}{key}:")
                lines.extend(_render_yaml(item, indent + 1))
                continue
            if isinstance(item, list):
                lines.append(f"{prefix}{key}: []")
                continue
            rendered = "" if item is None else _yaml_quote(str(item))
            lines.append(f"{prefix}{key}: {rendered}")

        if not lines:
            lines.append(f"{prefix}{{}}")
        return lines

    if isinstance(value, list):
        if not value:
            return [f"{prefix}[]"]

        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(_render_yaml(item, indent + 1))
            else:
                lines.append(f"{prefix}- {_yaml_quote(str(item))}")
        return lines

    return [f"{prefix}{_yaml_quote(str(value))}"]


@dataclass
class CaptionStyle:
    """Representation of caption localization details."""

    figure_template: str
    table_template: str
    figure_title: str
    table_title: str
    fig_prefix: List[str]
    tbl_prefix: List[str]
    title_delim: str

    @classmethod
    def default(cls) -> "CaptionStyle":
        """Return the default (English) caption style."""
        return cls(
            figure_template="Figure $$i$$$$titleDelim$$ $$t$$",
            table_template="Table $$i$$$$titleDelim$$ $$t$$",
            figure_title="",
            table_title="",
            fig_prefix=["Figure", "Figures"],
            tbl_prefix=["Table", "Tables"],
            title_delim=":",
        )

    @classmethod
    def from_locale(cls, locale: Optional[str]) -> "CaptionStyle":
        """Create a caption style from a locale hint."""
        if (
            locale is None
            or locale.strip() == ""
            or locale.lower() in {"en", "en-us", "en-gb"}
        ):
            return cls.default()

        if locale.lower() in {"zh", "zh-cn", "zh-hans", "zh-sg", "zh-tw"}:
            return cls(
                figure_template="图 $$i$$$$titleDelim$$ $$t$$",
                table_template="表 $$i$$$$titleDelim$$ $$t$$",
                figure_title="",
                table_title="",
                fig_prefix=["图", "图"],
                tbl_prefix=["表", "表"],
                title_delim="：",
            )

        return cls.default()

    def with_overrides(
        self,
        overrides: Optional[Dict[str, Union[str, List[str]]]],
    ) -> "CaptionStyle":
        """Return a copy of this style with overrides applied."""
        if not overrides:
            return self

        data = asdict(self)
        for key, value in overrides.items():
            if key in data and value is not None:
                data[key] = value
        return CaptionStyle(**data)

    def to_metadata(self) -> OrderedDict[str, Union[str, List[str]]]:
        """Render the style as ordered metadata keys."""
        ordered: OrderedDict[str, Union[str, List[str]]] = OrderedDict()
        ordered["figureTemplate"] = self.figure_template
        ordered["tableTemplate"] = self.table_template
        ordered["figureTitle"] = self.figure_title
        ordered["tableTitle"] = self.table_title
        ordered["figPrefix"] = list(self.fig_prefix)
        ordered["tblPrefix"] = list(self.tbl_prefix)
        ordered["titleDelim"] = self.title_delim
        return ordered

    def is_default(self) -> bool:
        """Return True if this style is the default English style."""
        return self == CaptionStyle.default()


@dataclass
class ConversionConfig:
    """Configuration for LaTeX to Word conversion."""

    input_texfile: Path
    output_docxfile: Path
    bibfile: Optional[Path] = None
    cslfile: Optional[Path] = None
    reference_docfile: Optional[Path] = None
    debug: bool = False
    fix_table: bool = False
    caption_style: CaptionStyle = field(default_factory=CaptionStyle.default)
    multifig_figenv_template: Optional[str] = None
    output_texfile: Path = field(init=False)
    temp_subtexfile_dir: Path = field(init=False)
    lua_filters: List[Path] = field(init=False, default_factory=list)
    author_lua_filters: List[Path] = field(init=False, default_factory=list)
    metadata_override_file: Optional[Path] = field(default=None, init=False)
    author_metadata: Optional[Dict[str, YamlValue]] = field(
        default=None,
        init=False,
    )
    bibliography_files: List[Path] = field(
        default_factory=list,
        init=False,
    )

    def __post_init__(self) -> None:
        """Initialize derived paths and validate configuration."""
        self.input_texfile = Path(self.input_texfile).resolve()
        self.output_docxfile = Path(self.output_docxfile).resolve()

        if self.bibfile is not None:
            self.bibfile = Path(self.bibfile).resolve()
        if self.cslfile is not None:
            self.cslfile = Path(self.cslfile).resolve()
        if self.reference_docfile is not None:
            self.reference_docfile = Path(self.reference_docfile).resolve()

        self._bibfile_explicit = self.bibfile is not None

        self.output_texfile = self.input_texfile.with_name(
            f"{self.input_texfile.stem}_modified.tex"
        )
        self.temp_subtexfile_dir = (
            self.input_texfile.parent / "temp_subtexfile_dir"
        )

        self._set_default_paths()
        self._initialize_bibliography_files()
        self._validate_input_files()

    def _reset_metadata_override(self) -> None:
        """Invalidate any generated metadata override file."""
        self.metadata_override_file = None

    def _set_default_paths(self) -> None:
        """Set default paths for optional files."""
        package_dir = Path(__file__).parent

        if self.bibfile is None:
            bib_files = list(self.input_texfile.parent.glob("*.bib"))
            if bib_files:
                self.bibfile = bib_files[0].resolve()

        if self.cslfile is None:
            self.cslfile = (package_dir / "ieee.csl").resolve()

        if self.reference_docfile is None:
            self.reference_docfile = (
                package_dir / "default_temp.docx"
            ).resolve()

        self.author_lua_filters = [
            (package_dir / "scholarly-metadata.lua").resolve(),
            (package_dir / "author-info-blocks.lua").resolve(),
        ]
        self.lua_filters = [
            (package_dir / "resolve_equation_labels.lua").resolve(),
        ]

    def _initialize_bibliography_files(self) -> None:
        """Prime the bibliography file collection."""
        self.bibliography_files = []
        if self.bibfile is not None:
            self._register_bibliography_path(self.bibfile)

    def _register_bibliography_path(self, path: Path) -> None:
        """Store a bibliography path if it is new."""
        resolved = Path(path).resolve()
        if resolved not in self.bibliography_files:
            self.bibliography_files.append(resolved)
        explicit = getattr(self, "_bibfile_explicit", False)
        if self.bibfile is None and not explicit:
            self.bibfile = resolved

    def _validate_input_files(self) -> None:
        """Validate that required input files exist."""
        if not self.input_texfile.exists():
            raise FileNotFoundError(
                f"Input TeX file not found: {self.input_texfile}"
            )

        missing_bibliographies = [
            str(path)
            for path in self.bibliography_files
            if not path.exists()
        ]
        for missing in missing_bibliographies:
            logging.warning("Bibliography file not found: %s", missing)

        if self.cslfile is not None and not self.cslfile.exists():
            raise FileNotFoundError(f"CSL file not found: {self.cslfile}")

        if (
            self.reference_docfile is not None
            and not self.reference_docfile.exists()
        ):
            raise FileNotFoundError(
                f"Reference document not found: {self.reference_docfile}"
            )

        if not self.lua_filters:
            raise FileNotFoundError("Lua filters not configured.")

        all_filters = self.lua_filters + self.author_lua_filters
        missing_filters = [
            str(path)
            for path in all_filters
            if not path.exists()
        ]
        if missing_filters:
            raise FileNotFoundError(
                "Lua filter not found: " + ", ".join(missing_filters)
            )

    def apply_caption_preferences(
        self,
        *,
        style: Optional[CaptionStyle] = None,
        locale: Optional[str] = None,
        overrides: Optional[Dict[str, Union[str, List[str]]]] = None,
    ) -> None:
        """Update caption localization preferences."""
        updated_style = style or self.caption_style

        if locale is not None:
            updated_style = CaptionStyle.from_locale(locale)

        if overrides:
            updated_style = updated_style.with_overrides(overrides)

        style_changed = (updated_style != self.caption_style) or (
            style is not None
        )
        self.caption_style = updated_style

        if style_changed or locale is not None or overrides:
            self._reset_metadata_override()

    def set_author_metadata(
        self,
        metadata: Optional[YamlValue],
    ) -> None:
        """Store parsed author metadata for later use."""

        if metadata is None:
            self.author_metadata = None
        else:
            from .authors import prepare_author_metadata

            normalized = prepare_author_metadata(metadata)
            if normalized and normalized.get("author"):
                self.author_metadata = normalized
            else:
                self.author_metadata = None
        self._reset_metadata_override()

    def set_detected_bibliography(self, path: Path) -> None:
        """Update bibliography path based on detected LaTeX commands."""

        resolved = Path(path).resolve()
        self.add_bibliography_file(resolved)

    def add_bibliography_file(self, path: Path) -> None:
        """Add a bibliography file to the configuration."""
        self._register_bibliography_path(path)

    def get_bibliography_files(self) -> List[Path]:
        """Return all configured bibliography files."""
        return list(self.bibliography_files)

    def iter_bibliography_files(self) -> Iterable[Path]:
        """Iterate over configured bibliography files."""
        return iter(self.bibliography_files)

    def has_bibliography(self) -> bool:
        """Return True when at least one bibliography file exists."""
        for path in self.bibliography_files:
            if path.exists() and path.is_file():
                return True
        return False

    def get_metadata_file(self) -> Path:
        """Return the metadata file to use for Pandoc."""
        needs_override = (
            not self.caption_style.is_default()
            or self.has_author_metadata()
        )

        if not needs_override:
            return PandocOptions.METADATA_FILE

        if (
            self.metadata_override_file is not None
            and self.metadata_override_file.exists()
        ):
            return self.metadata_override_file

        if self.temp_subtexfile_dir is None:
            raise RuntimeError("Temporary directory not initialized yet.")
        self.temp_subtexfile_dir.mkdir(parents=True, exist_ok=True)
        target = self.temp_subtexfile_dir / "pandoc_metadata_overrides.yaml"

        yaml_lines = self._build_metadata_yaml()
        target.write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
        self.metadata_override_file = target
        return target

    def _build_metadata_yaml(self) -> List[str]:
        """Construct YAML lines for the override metadata file."""
        metadata: OrderedDict[str, YamlValue] = OrderedDict()
        for key, value in self.caption_style.to_metadata().items():
            metadata[key] = value

        if self.author_metadata:
            author_section = self.author_metadata.get("author")
            if author_section is not None:
                metadata["author"] = author_section

            institute_section = self.author_metadata.get("institute")
            if institute_section is not None:
                metadata["institute"] = institute_section

            for extra_key, extra_value in self.author_metadata.items():
                if extra_key in {"author", "institute"}:
                    continue
                metadata[extra_key] = extra_value

        return _render_yaml(dict(metadata))

    def get_lua_filters(self) -> List[Path]:
        """Return Lua filters to use for the current configuration."""

        filters = list(self.lua_filters)
        if self.has_author_metadata():
            filters = list(self.author_lua_filters) + filters
        return filters

    def has_author_metadata(self) -> bool:
        """Return True when author metadata with entries is available."""

        if not self.author_metadata:
            return False

        authors = self.author_metadata.get("author")
        if isinstance(authors, list):
            return len(authors) > 0

        return False

    def get_multifig_template(self) -> str:
        """Get the multi-figure template to use."""
        return self.multifig_figenv_template or TexTemplates.MULTIFIG_FIGENV

    def setup_logger(self) -> logging.Logger:
        """Set up and return a logger instance."""
        logger = logging.getLogger(f"tex2docx_{uuid.uuid4().hex[:6]}")

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        return logger

    def log_paths(self, logger: logging.Logger) -> None:
        """Log configuration paths for debugging."""
        logger.debug("Input TeX file: %s", self.input_texfile)
        logger.debug("Output DOCX file: %s", self.output_docxfile)
        logger.debug("Output TeX file: %s", self.output_texfile)
        logger.debug("Temp directory: %s", self.temp_subtexfile_dir)
        logger.debug("Primary bibliography file: %s", self.bibfile)
        logger.debug(
            "Bibliography files: %s",
            [str(path) for path in self.bibliography_files],
        )
        logger.debug("CSL file: %s", self.cslfile)
        logger.debug("Reference document: %s", self.reference_docfile)
        logger.debug(
            "Lua filters: %s",
            [str(path) for path in self.get_lua_filters()],
        )
        logger.debug("Fix tables: %s", self.fix_table)
        logger.debug("Debug mode: %s", self.debug)
