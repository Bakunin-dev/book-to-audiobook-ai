"""Stable text contracts shared by reader, translator, QA and future repair."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from aitran.errors import SourceTextError

TEXT_CONTRACT_VERSION = "paragraph-blocks-v1"
PARAGRAPH_ID_PATTERN = r"P\d{6}"
_START_MARKER = re.compile(rf"^@@(?P<id>{PARAGRAPH_ID_PATTERN})@@[ \t]*$", re.MULTILINE)
_TAGGED_BLOCK = re.compile(
    rf"^@@(?P<id>{PARAGRAPH_ID_PATTERN})@@[ \t]*\r?\n"
    rf"(?P<body>.*?)\r?\n@@END-(?P=id)@@[ \t]*(?=\r?\n|\Z)",
    re.MULTILINE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class SourceParagraph:
    """One non-blank source block with a stable document-wide identifier."""

    paragraph_id: str
    text: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class TranslatedParagraph:
    paragraph_id: str
    text: str


@dataclass(frozen=True, slots=True)
class QAIssue:
    """Paragraph-addressed issue contract used by deterministic QA and repair."""

    code: str
    message: str
    paragraph_ids: tuple[str, ...]
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class RepairPatch:
    """A future repair may replace only the explicitly addressed paragraph."""

    paragraph_id: str
    replacement: str


class LexiconMode(StrEnum):
    AUTO = "auto"
    CONTEXTUAL = "contextual"
    SPOKEN = "spoken"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True, slots=True)
class LexiconEntry:
    """Stable semantic row contract for the future UTF-8 TSV lexicon."""

    source: str
    written_ru: str
    spoken_ru: str
    mode: LexiconMode
    aliases: tuple[str, ...] = ()
    note: str = ""


class ApprovedLexicon(Protocol):
    """Future resolvers expose only source-relevant approved rows to prompts."""

    def exact_matches(self, source_text: str) -> tuple[LexiconEntry, ...]:
        """Return longest-first exact/alias matches without fuzzy guessing."""


@dataclass(frozen=True, slots=True)
class TextBatch:
    """A source slice whose paragraphs retain document-wide IDs and offsets."""

    source_text: str
    start: int
    end: int
    paragraphs: tuple[SourceParagraph, ...]

    @property
    def paragraph_ids(self) -> tuple[str, ...]:
        return tuple(paragraph.paragraph_id for paragraph in self.paragraphs)

    def render_tagged_source(self) -> str:
        blocks = []
        for paragraph in self.paragraphs:
            blocks.append(
                f"@@{paragraph.paragraph_id}@@\n{paragraph.text}\n@@END-{paragraph.paragraph_id}@@"
            )
        return "\n\n".join(blocks)

    def render_translation(self, translations: tuple[TranslatedParagraph, ...]) -> str:
        expected = self.paragraph_ids
        actual = tuple(item.paragraph_id for item in translations)
        if actual != expected:
            raise ValueError("translation paragraph IDs do not match the source batch")

        translated_by_id = {item.paragraph_id: item.text for item in translations}
        cursor = self.start
        rendered: list[str] = []
        for paragraph in self.paragraphs:
            rendered.append(self.source_text[cursor - self.start : paragraph.start - self.start])
            rendered.append(translated_by_id[paragraph.paragraph_id].strip("\r\n"))
            cursor = paragraph.end
        rendered.append(self.source_text[cursor - self.start :])
        return "".join(rendered)

    def render_tagged_translation(
        self,
        translations: tuple[TranslatedParagraph, ...],
    ) -> str:
        expected = self.paragraph_ids
        actual = tuple(item.paragraph_id for item in translations)
        if actual != expected:
            raise ValueError("translation paragraph IDs do not match the source batch")
        return "\n\n".join(
            f"@@{item.paragraph_id}@@\n{item.text.strip(chr(13) + chr(10))}\n"
            f"@@END-{item.paragraph_id}@@"
            for item in translations
        )


@dataclass(frozen=True, slots=True)
class TextDocument:
    """Lossless source document with blank-line-delimited translation blocks."""

    text: str
    paragraphs: tuple[SourceParagraph, ...]

    @classmethod
    def from_text(cls, text: str) -> TextDocument:
        if not text.strip():
            raise SourceTextError("Исходная книга пуста или содержит только пробелы.")

        ranges: list[tuple[int, int]] = []
        cursor = 0
        block_start: int | None = None
        block_end = 0
        for line in text.splitlines(keepends=True):
            content = line.rstrip("\r\n")
            is_blank = not content.strip(" \t")
            if is_blank:
                if block_start is not None:
                    ranges.append((block_start, block_end))
                    block_start = None
            else:
                if block_start is None:
                    block_start = cursor
                block_end = cursor + len(content)
            cursor += len(line)

        if block_start is not None:
            ranges.append((block_start, block_end))

        if not ranges:
            raise SourceTextError("В исходной книге не найдено ни одного текстового абзаца.")

        paragraphs = tuple(
            SourceParagraph(
                paragraph_id=f"P{index:06d}",
                text=text[start:end],
                start=start,
                end=end,
            )
            for index, (start, end) in enumerate(ranges, start=1)
        )
        return cls(text=text, paragraphs=paragraphs)

    def slice(self, *, start: int, end: int) -> TextBatch:
        if not 0 <= start < end <= len(self.text):
            raise ValueError("document slice is outside the source text")

        crossing = [
            paragraph.paragraph_id
            for paragraph in self.paragraphs
            if (paragraph.start < start < paragraph.end) or (paragraph.start < end < paragraph.end)
        ]
        if crossing:
            raise SourceTextError("Граница батча пересекла текстовый абзац: " + ", ".join(crossing))

        selected = tuple(
            paragraph
            for paragraph in self.paragraphs
            if start <= paragraph.start and paragraph.end <= end
        )
        if not selected:
            raise SourceTextError("Батч не содержит ни одного текстового абзаца.")
        return TextBatch(
            source_text=self.text[start:end],
            start=start,
            end=end,
            paragraphs=selected,
        )


def recover_missing_end_markers(
    text: str, *, expected_ids: tuple[str, ...], finish_reason: str | None,
) -> str:
    """Recover only a fully ordered, normally finished start-only response."""
    if finish_reason != "stop" or "@@END" in text:
        return text
    starts = list(re.finditer(r"(?m)^@@(P\d{6})@@[ \t]*$", text))
    if (not starts or text[:starts[0].start()].strip()
        or tuple(m.group(1) for m in starts) != expected_ids):
        return text
    repaired: list[str] = []
    for index, marker in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        body = text[marker.end():end].strip("\r\n")
        if not body.strip() or "@@" in body:
            return text
        repaired.append(f"@@{marker.group(1)}@@\n{body}\n@@END-{marker.group(1)}@@")
    return "\n\n".join(repaired) + "\n"


def parse_tagged_translation(
    text: str,
    *,
    expected_ids: tuple[str, ...],
) -> tuple[tuple[TranslatedParagraph, ...], list[str]]:
    """Parse strict paragraph markers and report all structural defects."""

    cleaned = text.strip()
    parsed: list[TranslatedParagraph] = []
    errors: list[str] = []
    cursor = 0

    for match in _TAGGED_BLOCK.finditer(cleaned):
        outside = cleaned[cursor : match.start()]
        if outside.strip():
            errors.append("вне paragraph ID найден посторонний текст")
        body = match.group("body").strip("\r\n")
        paragraph_id = match.group("id")
        if not body.strip():
            errors.append(f"абзац {paragraph_id} пуст")
        parsed.append(TranslatedParagraph(paragraph_id=paragraph_id, text=body))
        cursor = match.end()

    if cleaned[cursor:].strip():
        errors.append("после последнего paragraph ID найден посторонний текст")
    if not parsed and (_START_MARKER.search(cleaned) or cleaned):
        errors.append("не удалось разобрать ни одного полного paragraph ID")
    if not cleaned:
        errors.append("получен пустой ответ")

    actual_ids = tuple(item.paragraph_id for item in parsed)
    if len(set(actual_ids)) != len(actual_ids):
        errors.append("paragraph ID повторяются")
    if actual_ids != expected_ids:
        missing = [paragraph_id for paragraph_id in expected_ids if paragraph_id not in actual_ids]
        unexpected = [
            paragraph_id for paragraph_id in actual_ids if paragraph_id not in expected_ids
        ]
        if missing:
            errors.append("пропущены paragraph ID: " + ", ".join(missing))
        if unexpected:
            errors.append("неожиданные paragraph ID: " + ", ".join(unexpected))
        if not missing and not unexpected:
            errors.append("нарушен порядок paragraph ID")

    return tuple(parsed), list(dict.fromkeys(errors))
