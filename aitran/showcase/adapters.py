"""Complete but deliberately simple substitutes for closed product engines."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
import math
import struct
from typing import Protocol
import wave

from aitran.artifacts import sha256_text
from aitran.contracts import TextDocument, TranslatedParagraph
from aitran.errors import DemoAdapterError
from aitran.showcase.fixtures import ROLE_BY_ID, SOURCE_SHA256, TRANSLATED_BY_ID
from aitran.showcase.models import AudioScene, CastLine


class TranslationPort(Protocol):
    def translate(self, document: TextDocument) -> tuple[TranslatedParagraph, ...]: ...


class CastPort(Protocol):
    def analyze(self, paragraphs: Sequence[TranslatedParagraph]) -> tuple[CastLine, ...]: ...


class AudioRendererPort(Protocol):
    def render(self, scene: AudioScene) -> bytes: ...


class FixtureTranslator:
    """Fixture-only adapter; it is not a model and makes no network calls."""

    def translate(self, document: TextDocument) -> tuple[TranslatedParagraph, ...]:
        if sha256_text(document.text) != SOURCE_SHA256:
            raise DemoAdapterError(
                "Публичный адаптер переводит только встроенную синтетическую книгу."
            )
        expected = tuple(paragraph.paragraph_id for paragraph in document.paragraphs)
        if expected != tuple(TRANSLATED_BY_ID):
            raise DemoAdapterError("Структура синтетической книги не совпала с fixture.")
        return tuple(
            TranslatedParagraph(paragraph_id=paragraph_id, text=TRANSLATED_BY_ID[paragraph_id])
            for paragraph_id in expected
        )


class FixtureCastAnalyzer:
    """Return fixed source-grounded roles for the included fictional scene."""

    def analyze(self, paragraphs: Sequence[TranslatedParagraph]) -> tuple[CastLine, ...]:
        actual = tuple(paragraph.paragraph_id for paragraph in paragraphs)
        if actual != tuple(ROLE_BY_ID):
            raise DemoAdapterError("Cast fixture не соответствует переведённым абзацам.")
        return tuple(
            CastLine(item.paragraph_id, ROLE_BY_ID[item.paragraph_id], item.text)
            for item in paragraphs
        )


class SyntheticWaveRenderer:
    """Create tiny deterministic tone WAVs; this is intentionally not speech."""

    sample_rate = 8_000
    duration_seconds = 0.18
    frequency_by_role = {
        "narrator": 440,
        "male_dialogue": 330,
        "female_dialogue": 550,
    }
    voice_by_role = {
        "narrator": "demo_narrator",
        "male_dialogue": "demo_male",
        "female_dialogue": "demo_female",
    }

    def render(self, scene: AudioScene) -> bytes:
        if scene.role not in self.frequency_by_role:
            raise DemoAdapterError(f"Неизвестная синтетическая роль: {scene.role}")
        if scene.voice != self.voice_by_role[scene.role]:
            raise DemoAdapterError("Голос не соответствует роли в демонстрационном плане.")
        frequency = self.frequency_by_role[scene.role] + int(scene.text_sha256[:2], 16) % 24
        frame_count = int(self.sample_rate * self.duration_seconds)
        frames = bytearray()
        for index in range(frame_count):
            envelope = min(1.0, index / 80, (frame_count - index) / 80)
            sample = int(5_500 * envelope * math.sin(2 * math.pi * frequency * index / self.sample_rate))
            frames.extend(struct.pack("<h", sample))
        buffer = BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.sample_rate)
            output.writeframes(bytes(frames))
        return buffer.getvalue()
