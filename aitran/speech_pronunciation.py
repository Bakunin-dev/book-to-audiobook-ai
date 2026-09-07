"""Explicit book pronunciations, applied after automatic stress without rewriting words."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from aitran.errors import SourceTextError

_VOWELS = frozenset("аеёиоуыэюяАЕЁИОУЫЭЮЯ")
_LETTER = r"А-Яа-яЁё"


@dataclass(frozen=True)
class Pronunciation:
    written: str
    stressed: str

    def validate(self) -> None:
        if (
            not self.written.strip()
            or "+" in self.written
            or self.stressed.replace("+", "") != self.written
            or any(c in self.written for c in "\r\n\t")
            or not re.fullmatch(r"[А-Яа-яЁё][А-Яа-яЁё ,—-]*", self.written)
            or not any(c in _VOWELS for c in self.written)
        ):
            raise SourceTextError("Произношение может менять только позиции + в русском тексте.")
        for index, char in enumerate(self.stressed):
            if char == "+" and (
                index + 1 == len(self.stressed) or self.stressed[index + 1] not in _VOWELS
            ):
                raise SourceTextError("Метка + должна стоять непосредственно перед гласной.")


def load_pronunciations(path: Path | None) -> tuple[Pronunciation, ...]:
    if path is None:
        return ()
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict) or value.get("schema_version") != "aitran-pronunciation-v1":
            raise ValueError("schema")
        raw_entries = value["entries"]
        if not isinstance(raw_entries, list):
            raise ValueError("entries")
        entries = tuple(Pronunciation(**row) for row in raw_entries)
        seen = set()
        for entry in entries:
            entry.validate()
            key = entry.written.casefold()
            if key in seen:
                raise ValueError("duplicate pronunciation")
            seen.add(key)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SourceTextError(f"Не удалось прочитать книжные произношения {path}: {exc}") from exc
    return entries


def apply_pronunciations(text: str, entries: tuple[Pronunciation, ...]) -> tuple[str, int]:
    """Exact word-bounded, longest-first matches; retain casing and all other accents."""
    if not entries:
        return text, 0
    for entry in entries:
        entry.validate()
    # Map visible offsets back to the accented input so untouched text is copied exactly.
    visible, starts = [], []
    pending = None
    for index, char in enumerate(text):
        if char == "+":
            if pending is None:
                pending = index
            continue
        starts.append(index if pending is None else pending)
        visible.append(char)
        pending = None
    plain = "".join(visible)
    lookup = {e.written.casefold(): e for e in entries}
    alternatives = "|".join(
        re.escape(e.written) for e in sorted(entries, key=lambda e: -len(e.written))
    )
    pattern = re.compile(rf"(?<![{_LETTER}])(?:{alternatives})(?![{_LETTER}])", re.IGNORECASE)
    pieces, cursor, matches = [], 0, 0
    for match in pattern.finditer(plain):
        start = starts[match.start()]
        end = starts[match.end()] if match.end() < len(starts) else len(text)
        pieces.append(text[cursor:start])
        template = lookup[match.group().casefold()].stressed
        offset = 0
        for char in template:
            if char == "+":
                pieces.append("+")
            else:
                pieces.append(match.group()[offset])
                offset += 1
        cursor = end
        matches += 1
    pieces.append(text[cursor:])
    result = "".join(pieces)
    assert result.replace("+", "") == text.replace("+", "")
    return result, matches
