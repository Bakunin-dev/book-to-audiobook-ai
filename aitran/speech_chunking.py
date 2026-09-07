"""Deterministic chapter-aware splitting for bounded TTS requests."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from aitran.errors import SourceTextError

SPEECH_CHUNKER_VERSION = "speech-chunking-v1"

_MARKDOWN_HEADING = re.compile(
    r"(?m)^[ \t]{0,3}#{1,6}[ \t]+(?P<title>[^\r\n]+?)[ \t]*#*[ \t]*(?=\r?$)"
)
_PLAIN_CHAPTER_HEADING = re.compile(
    r"(?im)^[ \t]*(?P<title>(?:глава|часть|пролог|эпилог|интерлюдия)\b[^\r\n]*)"
    r"[ \t]*(?=\r?$)"
)
_SPEECH_BOUNDARY = re.compile(
    r"(?:\r?\n|[.!?…;:][\"'»”’)]*[ \t]+)",
    re.UNICODE,
)
_WHITESPACE_BOUNDARY = re.compile(r"\s+", re.UNICODE)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class SpeechChapter:
    index: int
    title: str
    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class SpeechChunk:
    index: int
    chapter_index: int
    chapter_title: str
    part_index: int
    start: int
    end: int
    text: str
    sha256: str


def _heading_matches(text: str) -> list[tuple[int, str]]:
    matches: list[tuple[int, str]] = []
    for pattern in (_MARKDOWN_HEADING, _PLAIN_CHAPTER_HEADING):
        for match in pattern.finditer(text):
            title = match.group("title").strip().rstrip("#").strip()
            matches.append((match.start(), title))
    matches.sort(key=lambda item: item[0])

    deduplicated: list[tuple[int, str]] = []
    for start, title in matches:
        if deduplicated and deduplicated[-1][0] == start:
            continue
        deduplicated.append((start, title))
    return deduplicated


def split_speech_chapters(text: str) -> list[SpeechChapter]:
    """Split Markdown/plain Russian chapter headings without dropping characters."""

    if not text.strip():
        raise SourceTextError("Файл готового перевода пуст или содержит только пробелы.")

    matches = _heading_matches(text)
    if not matches:
        return [SpeechChapter(index=0, title="Книга", start=0, end=len(text), text=text)]

    spans: list[tuple[int, int, str]] = []
    first_start = matches[0][0]
    if first_start > 0 and text[:first_start].strip():
        spans.append((0, first_start, "Вступление"))
    else:
        matches[0] = (0, matches[0][1])

    for position, (start, title) in enumerate(matches):
        end = matches[position + 1][0] if position + 1 < len(matches) else len(text)
        spans.append((start, end, title or f"Раздел {position + 1}"))

    chapters = [
        SpeechChapter(index=index, title=title, start=start, end=end, text=text[start:end])
        for index, (start, end, title) in enumerate(spans)
    ]
    if "".join(chapter.text for chapter in chapters) != text:
        raise AssertionError("lossless chapter splitting invariant failed")
    return chapters


def _split_oversized_unit(text: str, *, max_characters: int) -> list[str]:
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_characters:
        window = remaining[:max_characters]
        minimum = max(1, max_characters // 2)
        preferred = [match.end() for match in _SPEECH_BOUNDARY.finditer(window)]
        cut = next((position for position in reversed(preferred) if position >= minimum), None)
        if cut is None:
            whitespace = [match.end() for match in _WHITESPACE_BOUNDARY.finditer(window)]
            cut = next((position for position in reversed(whitespace) if position >= minimum), None)
        cut = cut or max_characters
        pieces.append(remaining[:cut])
        remaining = remaining[cut:]
    if remaining:
        pieces.append(remaining)
    return pieces


def _bounded_units(text: str, *, max_characters: int) -> list[str]:
    units: list[str] = []
    for line in text.splitlines(keepends=True):
        if len(line) <= max_characters:
            units.append(line)
        else:
            units.extend(_split_oversized_unit(line, max_characters=max_characters))
    if text and not units:
        units.extend(_split_oversized_unit(text, max_characters=max_characters))
    return units


def _chunk_chapter(
    chapter: SpeechChapter,
    *,
    target_characters: int,
    max_characters: int,
) -> list[str]:
    units = _bounded_units(chapter.text, max_characters=max_characters)
    chunks: list[str] = []
    current = ""

    for unit in units:
        if not current:
            current = unit
            continue
        combined_length = len(current) + len(unit)
        accept_soft_overflow = (
            len(current) < int(target_characters * 0.70) and combined_length <= max_characters
        )
        if combined_length <= target_characters or accept_soft_overflow:
            current += unit
        else:
            chunks.append(current)
            current = unit
    if current:
        chunks.append(current)

    if len(chunks) >= 2:
        tail = chunks[-1]
        merged = chunks[-2] + tail
        if len(tail) < int(target_characters * 0.30) and len(merged) <= max_characters:
            chunks[-2:] = [merged]

    if "".join(chunks) != chapter.text:
        raise AssertionError("lossless speech chunking invariant failed")
    if any(len(chunk) > max_characters for chunk in chunks):
        raise AssertionError("speech chunk exceeded configured character ceiling")
    return chunks


def chunk_speech_text(
    text: str,
    *,
    target_characters: int,
    max_characters: int,
) -> list[SpeechChunk]:
    """Return ordered, lossless, chapter-bounded TTS chunks."""

    if not 0 < target_characters <= max_characters:
        raise ValueError("target_characters must be positive and <= max_characters")

    chapters = split_speech_chapters(text)
    chunks: list[SpeechChunk] = []
    for chapter in chapters:
        cursor = chapter.start
        for part_index, chunk_text in enumerate(
            _chunk_chapter(
                chapter,
                target_characters=target_characters,
                max_characters=max_characters,
            )
        ):
            end = cursor + len(chunk_text)
            chunks.append(
                SpeechChunk(
                    index=len(chunks),
                    chapter_index=chapter.index,
                    chapter_title=chapter.title,
                    part_index=part_index,
                    start=cursor,
                    end=end,
                    text=chunk_text,
                    sha256=_sha256(chunk_text),
                )
            )
            cursor = end
        if cursor != chapter.end:
            raise AssertionError("speech chapter offsets are inconsistent")

    if "".join(chunk.text for chunk in chunks) != text:
        raise AssertionError("lossless book speech chunking invariant failed")
    return chunks
