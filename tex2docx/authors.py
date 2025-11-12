"""Utilities for extracting author metadata from LaTeX sources."""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from typing import DefaultDict, Dict, Iterable, List, Optional, Tuple

import regex  # type: ignore[import]

from .config import YamlValue


@dataclass
class _CommandInstance:
    """Representation of a LaTeX command invocation."""

    optional: Optional[str]
    argument: str


@dataclass
class _AuthorRecord:
    """Intermediate representation of an author's structured data."""

    name: str
    institutes: List[YamlValue]
    notes: List[str]
    extras: OrderedDict[str, YamlValue]


_TOKEN_PATTERN = regex.compile(r"\\thanks|\$[^$]+\$|\\[a-zA-Z]+|\w+|\*")
_THANKS_PATTERN = regex.compile(r"\\thanks\{(?:[^{}]+|(?R))*\}")


def parse_author_metadata(content: str) -> Optional[YamlValue]:
    """Parse author and affiliation data from LaTeX content."""

    if not content:
        return None

    author_commands = list(_iter_commands(content, "author"))
    if not author_commands:
        return None

    authors: List[Tuple[str, Optional[str]]] = []
    for command in author_commands:
        for name in _split_author_names(command.argument):
            if name:
                authors.append((name, command.optional))

    if not authors:
        return None

    affil_commands = list(_iter_commands(content, "affil"))
    affiliation_map: DefaultDict[str, List[str]] = defaultdict(list)
    note_map: DefaultDict[str, List[str]] = defaultdict(list)
    default_affiliations: List[str] = []

    for affil in affil_commands:
        text = _normalize_latex_text(affil.argument)
        if not text:
            continue

        tokens = _split_markers(affil.optional)
        if not tokens:
            _append_unique(default_affiliations, text)
            continue

        for marker in tokens:
            if _is_note_marker(marker):
                _append_unique_list(note_map[marker], text)
            else:
                _append_unique_list(affiliation_map[marker], text)

    records: List[_AuthorRecord] = []

    for name, marker_text in authors:
        clean_name, thanks_notes = _extract_thanks(name)
        normalized_name = _normalize_latex_text(clean_name)
        if not normalized_name:
            continue

        institutes: List[str] = []
        notes: List[str] = list(thanks_notes)

        tokens = _split_markers(marker_text)
        if tokens:
            for token in tokens:
                for item in affiliation_map.get(token, []):
                    _append_unique(institutes, item)
                for note in note_map.get(token, []):
                    _append_unique(notes, note)

        if not institutes and default_affiliations:
            institutes.extend(default_affiliations)

        record = _AuthorRecord(
            name=normalized_name,
            institutes=list(institutes),
            notes=notes,
            extras=OrderedDict(),
        )
        records.append(record)

    if not records:
        return None

    return _canonicalize_author_records(records)


def _iter_commands(content: str, name: str) -> Iterable[_CommandInstance]:
    """Yield all invocations of ``\name`` with optional arguments."""

    command = f"\\{name}"
    position = 0
    length = len(content)
    while True:
        index = content.find(command, position)
        if index == -1:
            break

        cursor = index + len(command)
        while cursor < length and content[cursor].isspace():
            cursor += 1

        optional: Optional[str] = None
        if cursor < length and content[cursor] == "[":
            optional, cursor = _extract_enclosed(content, cursor, "[", "]")
            while cursor < length and content[cursor].isspace():
                cursor += 1

        if cursor >= length or content[cursor] != "{":
            position = cursor
            continue

        argument, cursor = _extract_enclosed(content, cursor, "{", "}")
        yield _CommandInstance(optional=optional, argument=argument)
        position = cursor


def _extract_enclosed(
    text: str,
    start: int,
    opening: str,
    closing: str,
) -> Tuple[str, int]:
    """Extract content within balanced delimiters starting at ``start``."""

    assert text[start] == opening
    depth = 0
    cursor = start
    length = len(text)

    while cursor < length:
        char = text[cursor]
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start + 1:cursor], cursor + 1
        elif char == "\\" and cursor + 1 < length:
            cursor += 1  # Skip escaped character
        cursor += 1

    raise ValueError("Unbalanced delimiters when parsing LaTeX command")


def _split_author_names(argument: str) -> List[str]:
    """Split an ``\author`` body into individual author names."""

    if not argument:
        return []

    candidates: List[str] = []
    for part in regex.split(r"\\and", argument):
        for segment in regex.split(r"\\\\", part):
            clean = segment.strip()
            if clean:
                candidates.append(clean)
    return candidates


def _split_markers(optional: Optional[str]) -> List[str]:
    """Split an optional argument listing affiliation markers."""

    if optional is None:
        return []

    cleaned = optional.replace(" ", "").replace("\n", "")
    tokens = _TOKEN_PATTERN.findall(cleaned)
    results: List[str] = []
    for token in tokens:
        if token == "\\thanks":
            continue
        stripped = token.strip()
        if stripped and stripped not in {",", ";"}:
            results.append(stripped)
    return results


def _normalize_latex_text(value: str) -> str:
    """Normalize LaTeX text fragments to plain text."""

    if not value:
        return ""

    text = value.replace("\\\\", " ")
    text = text.replace("~", " ")
    text = text.replace("\n", " ")
    text = regex.sub(r"\\", "", text)
    text = regex.sub(r"[{}]", "", text)
    text = regex.sub(r"\s+", " ", text)
    return text.strip()


def _extract_thanks(name: str) -> Tuple[str, List[str]]:
    """Remove ``\thanks`` blocks and collect their contents."""

    if not name:
        return "", []

    notes: List[str] = []

    def _collect(match: regex.Match) -> str:
        raw = match.group(0)
        brace_index = raw.find("{")
        inner = raw[brace_index + 1:-1]
        normalized = _normalize_latex_text(inner)
        if normalized:
            notes.append(normalized)
        return ""

    cleaned = _THANKS_PATTERN.sub(_collect, name)
    return cleaned, notes


def _append_unique(container: List[str], value: str) -> None:
    """Append ``value`` to ``container`` if not already present."""

    if value not in container:
        container.append(value)


def _append_unique_list(container: List[str], value: str) -> None:
    """Append to list ensuring uniqueness."""

    _append_unique(container, value)


def _is_note_marker(marker: str) -> bool:
    """Determine whether a marker should be treated as a note indicator."""

    if not marker:
        return False
    return bool(regex.search(r"[^0-9A-Za-z]", marker))


def _canonicalize_author_records(
    records: List[_AuthorRecord],
    seed_institutes: Optional[Iterable[YamlValue]] = None,
) -> Optional[Dict[str, YamlValue]]:
    """Convert intermediate author records into canonical Pandoc metadata."""

    if not records:
        return None

    institute_store: OrderedDict[str, OrderedDict[str, YamlValue]] = (
        OrderedDict()
    )
    name_index: Dict[str, str] = {}

    def _register_institute(raw: YamlValue) -> Optional[str]:
        if raw is None:
            return None

        if isinstance(raw, dict):
            entry = OrderedDict(raw)
            if "id" in entry or "name" in entry or len(entry) > 1:
                inst_id = str(
                    entry.get("id")
                    or f"affiliation-{len(institute_store) + 1}"
                )
                existing = institute_store.get(inst_id)
                if existing is None:
                    existing = OrderedDict()
                    existing["id"] = inst_id
                    institute_store[inst_id] = existing
                for key, value in entry.items():
                    if key == "id":
                        continue
                    if key not in existing:
                        existing[key] = value
                if "name" not in existing:
                    existing["name"] = inst_id
                name_value = existing.get("name")
                if isinstance(name_value, str) and name_value:
                    name_index.setdefault(name_value, inst_id)
                return inst_id

            if len(entry) == 1:
                key, value = next(iter(entry.items()))
                nested_entry = OrderedDict()
                nested_entry["id"] = str(key)
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        nested_entry[sub_key] = sub_value
                else:
                    nested_entry["name"] = value
                return _register_institute(nested_entry)

            return None

        text = str(raw).strip()
        if not text:
            return None
        if text in institute_store:
            return text
        if text in name_index:
            return name_index[text]

        inst_id = f"affiliation-{len(institute_store) + 1}"
        entry = OrderedDict([("id", inst_id), ("name", text)])
        institute_store[inst_id] = entry
        name_index.setdefault(text, inst_id)
        return inst_id

    if seed_institutes:
        for seed in seed_institutes:
            _register_institute(seed)

    authors_output: List[YamlValue] = []

    for record in records:
        entry = OrderedDict()
        entry["name"] = record.name

        institute_ids: List[str] = []
        for raw_inst in record.institutes:
            inst_id = _register_institute(raw_inst)
            if inst_id and inst_id not in institute_ids:
                institute_ids.append(inst_id)
        if institute_ids:
            entry["institute"] = institute_ids

        extras = OrderedDict(record.extras)
        if "note" in extras:
            sanitized_note = _stringify_note(extras["note"])
            if sanitized_note:
                extras["note"] = sanitized_note
            else:
                extras.pop("note")

        if record.notes:
            combined_note = "; ".join(record.notes)
            if (
                "note" in extras
                and isinstance(extras["note"], str)
                and extras["note"]
            ):
                extras["note"] = extras["note"] + "; " + combined_note
            else:
                extras["note"] = combined_note

        for key, value in extras.items():
            entry[key] = value

        authors_output.append(entry)

    metadata: OrderedDict[str, YamlValue] = OrderedDict()
    metadata["author"] = authors_output
    metadata["institute"] = (
        list(institute_store.values()) if institute_store else []
    )
    return metadata


def _normalize_author_entries(source: YamlValue) -> List[YamlValue]:
    if source is None:
        return []
    if isinstance(source, list):
        return list(source)
    return [source]


def _normalize_institute_seed(seed: YamlValue) -> List[YamlValue]:
    if seed is None:
        return []
    if isinstance(seed, list):
        return list(seed)
    return [seed]


def _record_from_metadata_item(item: YamlValue) -> Optional[_AuthorRecord]:
    if item is None:
        return None

    if isinstance(item, str):
        name = item.strip()
        if not name:
            return None
        return _AuthorRecord(
            name=name,
            institutes=[],
            notes=[],
            extras=OrderedDict(),
        )

    if isinstance(item, dict):
        working = OrderedDict(item)
        name_value: Optional[str] = None

        if "name" in working:
            candidate = working.pop("name")
            name_value = str(candidate).strip()
        elif len(working) == 1:
            key, value = next(iter(working.items()))
            name_value = str(key).strip()
            if isinstance(value, dict):
                working = OrderedDict(value)
            else:
                working = OrderedDict({"affiliation": value})
        else:
            candidate = working.pop("name", None)
            if candidate is not None:
                name_value = str(candidate).strip()

        if not name_value:
            fallback = str(item).strip()
            if not fallback:
                return None
            return _AuthorRecord(
                name=fallback,
                institutes=[],
                notes=[],
                extras=OrderedDict(),
            )

        institute_value = working.pop("institute", None)
        if institute_value is None and "affiliation" in working:
            institute_value = working.pop("affiliation")
        if institute_value is None and "affiliations" in working:
            institute_value = working.pop("affiliations")

        institutes = _flatten_institute_values(institute_value)

        note_value = working.get("note")
        notes: List[str] = []
        if note_value is not None:
            sanitized = _stringify_note(note_value)
            if sanitized:
                working["note"] = sanitized
                notes.append(sanitized)
            else:
                working.pop("note", None)

        extras = OrderedDict(working)

        return _AuthorRecord(
            name=name_value,
            institutes=institutes,
            notes=notes,
            extras=extras,
        )

    fallback_name = str(item).strip()
    if not fallback_name:
        return None
    return _AuthorRecord(
        name=fallback_name,
        institutes=[],
        notes=[],
        extras=OrderedDict(),
    )


def _flatten_institute_values(value: YamlValue) -> List[YamlValue]:
    if value is None:
        return []
    if isinstance(value, list):
        flattened: List[YamlValue] = []
        for item in value:
            flattened.extend(_flatten_institute_values(item))
        return flattened
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(";") if part.strip()]
        return parts or [value.strip()]
    return [value]


def _stringify_note(value: YamlValue) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        parts = [
            segment
            for segment in (_stringify_note(v) for v in value)
            if segment
        ]
        return "; ".join(parts)
    return str(value).strip()


def prepare_author_metadata(
    metadata: YamlValue,
) -> Optional[Dict[str, YamlValue]]:
    """Normalize user-supplied author metadata to canonical structure."""

    if metadata is None:
        return None

    def _build_records(source: YamlValue) -> List[_AuthorRecord]:
        records: List[_AuthorRecord] = []
        for item in _normalize_author_entries(source):
            record = _record_from_metadata_item(item)
            if record:
                records.append(record)
        return records

    if isinstance(metadata, dict) and (
        "author" in metadata or "institute" in metadata
    ):
        records = _build_records(metadata.get("author"))
        seed = _normalize_institute_seed(metadata.get("institute"))
        return _canonicalize_author_records(records, seed)

    records = _build_records(metadata)
    if not records:
        return None
    return _canonicalize_author_records(records)

