"""Small public contracts for the synthetic vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Stage(StrEnum):
    IMPORT = "import"
    TRANSLATE = "translate"
    VERIFY = "verify"
    CAST = "cast"
    AUDIO_PLAN = "audio-plan"
    RENDER = "render"


STAGE_ORDER = (
    Stage.IMPORT,
    Stage.TRANSLATE,
    Stage.VERIFY,
    Stage.CAST,
    Stage.AUDIO_PLAN,
    Stage.RENDER,
)


@dataclass(frozen=True, slots=True)
class PipelineEvent:
    stage: Stage
    action: str
    detail: str


@dataclass(frozen=True, slots=True)
class CastLine:
    paragraph_id: str
    role: str
    text: str


@dataclass(frozen=True, slots=True)
class AudioScene:
    scene_id: str
    paragraph_id: str
    role: str
    voice: str
    text: str
    text_sha256: str


@dataclass(frozen=True, slots=True)
class PipelineSummary:
    workspace: Path
    events: tuple[PipelineEvent, ...]
    chapter_count: int
    scene_count: int
    audio_files: tuple[Path, ...]
    status_file: Path
