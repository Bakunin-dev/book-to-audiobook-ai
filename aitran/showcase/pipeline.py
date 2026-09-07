"""Checkpointed executable vertical slice backed only by synthetic adapters."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from aitran.artifacts import atomic_write_bytes, atomic_write_json, atomic_write_text, sha256_text
from aitran.contracts import TextDocument, parse_tagged_translation
from aitran.errors import DemoAdapterError, DemoInterrupted, WorkspaceConflictError
from aitran.process_lock import exclusive_run
from aitran.showcase.adapters import FixtureCastAnalyzer, FixtureTranslator, SyntheticWaveRenderer
from aitran.showcase.fixtures import FIXTURE_ID, PRONUNCIATIONS, SOURCE_BOOK, SOURCE_SHA256
from aitran.showcase.models import AudioScene, PipelineEvent, PipelineSummary, Stage, STAGE_ORDER
from aitran.speech_chunking import chunk_speech_text, split_speech_chapters
from aitran.speech_pronunciation import apply_pronunciations

SCHEMA_VERSION = "potter-showcase-state-v1"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkspaceConflictError(f"Не удалось прочитать checkpoint {path.name}.") from exc
    if not isinstance(value, dict):
        raise WorkspaceConflictError(f"Checkpoint {path.name} имеет неверный формат.")
    return value


def _artifact_hashes(workspace: Path, names: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in names:
        path = workspace / name
        if not path.is_file() or path.is_symlink():
            raise WorkspaceConflictError(f"Не найден артефакт этапа: {name}")
        result[name] = _sha256_bytes(path.read_bytes())
    return result


def _validate_artifacts(workspace: Path, record: dict[str, Any]) -> None:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise WorkspaceConflictError("Checkpoint этапа не содержит проверяемых артефактов.")
    for name, expected in artifacts.items():
        path = workspace / name
        if (
            not isinstance(name, str)
            or not isinstance(expected, str)
            or not path.is_file()
            or path.is_symlink()
            or _sha256_bytes(path.read_bytes()) != expected
        ):
            raise WorkspaceConflictError(f"Артефакт изменён или отсутствует: {name}")


def _new_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_id": FIXTURE_ID,
        "source_sha256": SOURCE_SHA256,
        "status": "new",
        "completed": {},
    }


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _new_state()
    state = _read_json(path)
    if (
        state.get("schema_version") != SCHEMA_VERSION
        or state.get("fixture_id") != FIXTURE_ID
        or state.get("source_sha256") != SOURCE_SHA256
        or not isinstance(state.get("completed"), dict)
    ):
        raise WorkspaceConflictError("Workspace принадлежит другой версии демонстрации.")
    return state


def _source_document(workspace: Path) -> TextDocument:
    text = (workspace / "source.md").read_text(encoding="utf-8")
    if sha256_text(text) != SOURCE_SHA256:
        raise WorkspaceConflictError("Исходная книга изменилась после импорта.")
    return TextDocument.from_text(text)


def _translated_paragraphs(workspace: Path, document: TextDocument):
    tagged = (workspace / "translation.tagged.md").read_text(encoding="utf-8")
    expected = tuple(item.paragraph_id for item in document.paragraphs)
    paragraphs, errors = parse_tagged_translation(tagged, expected_ids=expected)
    if errors:
        raise WorkspaceConflictError("Структурная проверка перевода не пройдена: " + "; ".join(errors))
    return paragraphs


def _run_import(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    atomic_write_text(workspace / "source.md", SOURCE_BOOK)
    document = TextDocument.from_text(SOURCE_BOOK)
    manifest = {
        "schema_version": "potter-showcase-source-v1",
        "fixture_id": FIXTURE_ID,
        "source_sha256": SOURCE_SHA256,
        "paragraph_count": len(document.paragraphs),
        "immutable": True,
    }
    atomic_write_json(workspace / "source-manifest.json", manifest)
    return ["source.md", "source-manifest.json"], {
        "paragraphs": len(document.paragraphs),
        "source_immutable": True,
    }


def _run_translate(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    document = _source_document(workspace)
    translations = FixtureTranslator().translate(document)
    batch = document.slice(start=0, end=len(document.text))
    atomic_write_text(workspace / "translation.md", batch.render_translation(translations))
    atomic_write_text(
        workspace / "translation.tagged.md",
        batch.render_tagged_translation(translations) + "\n",
    )
    atomic_write_json(
        workspace / "translation-manifest.json",
        {
            "schema_version": "potter-showcase-translation-v1",
            "adapter": "fixture-only",
            "network_calls": 0,
            "paragraph_count": len(translations),
            "source_sha256": SOURCE_SHA256,
        },
    )
    return ["translation.md", "translation.tagged.md", "translation-manifest.json"], {
        "paragraphs": len(translations),
        "network_calls": 0,
    }


def _run_verify(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    document = _source_document(workspace)
    paragraphs = _translated_paragraphs(workspace, document)
    batch = document.slice(start=0, end=len(document.text))
    rendered = batch.render_translation(paragraphs)
    if rendered != (workspace / "translation.md").read_text(encoding="utf-8"):
        raise WorkspaceConflictError("Обычный и размеченный перевод расходятся.")
    report = {
        "schema_version": "potter-showcase-verification-v1",
        "paragraph_ids_preserved": True,
        "source_sha256_preserved": sha256_text(document.text) == SOURCE_SHA256,
        "structural_issues": 0,
    }
    atomic_write_json(workspace / "verification.json", report)
    return ["verification.json"], report


def _run_cast(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    document = _source_document(workspace)
    paragraphs = _translated_paragraphs(workspace, document)
    cast = FixtureCastAnalyzer().analyze(paragraphs)
    roles = sorted({item.role for item in cast})
    atomic_write_json(
        workspace / "cast.json",
        {
            "schema_version": "potter-showcase-cast-v1",
            "adapter": "fixture-only",
            "roles": roles,
            "lines": [asdict(item) for item in cast],
        },
    )
    return ["cast.json"], {"lines": len(cast), "roles": roles}


def _run_audio_plan(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    raw = _read_json(workspace / "cast.json")
    lines = raw.get("lines")
    if not isinstance(lines, list) or not lines:
        raise WorkspaceConflictError("Cast manifest не содержит реплик.")
    renderer = SyntheticWaveRenderer()
    scenes: list[AudioScene] = []
    pronunciation_matches = 0
    for row in lines:
        if not isinstance(row, dict):
            raise WorkspaceConflictError("Cast manifest содержит неверную строку.")
        stressed, count = apply_pronunciations(str(row["text"]), PRONUNCIATIONS)
        pronunciation_matches += count
        chunks = chunk_speech_text(stressed + "\n", target_characters=96, max_characters=150)
        for chunk in chunks:
            scene_id = f"S{len(scenes) + 1:04d}"
            role = str(row["role"])
            scenes.append(
                AudioScene(
                    scene_id=scene_id,
                    paragraph_id=str(row["paragraph_id"]),
                    role=role,
                    voice=renderer.voice_by_role[role],
                    text=chunk.text,
                    text_sha256=sha256_text(chunk.text),
                )
            )
    plan = {
        "schema_version": "potter-showcase-audio-plan-v1",
        "renderer": "synthetic-tones-not-speech",
        "pronunciation_matches": pronunciation_matches,
        "scenes": [asdict(scene) for scene in scenes],
    }
    atomic_write_json(workspace / "audio-plan.json", plan)
    return ["audio-plan.json"], {
        "scenes": len(scenes),
        "voices": len({scene.voice for scene in scenes}),
        "pronunciation_matches": pronunciation_matches,
    }


def _run_render(workspace: Path) -> tuple[list[str], dict[str, Any]]:
    raw = _read_json(workspace / "audio-plan.json")
    rows = raw.get("scenes")
    if not isinstance(rows, list) or not rows:
        raise WorkspaceConflictError("Audio plan не содержит сцен.")
    renderer = SyntheticWaveRenderer()
    rendered = reused = 0
    audio_names: list[str] = []
    for row in rows:
        scene = AudioScene(**row)
        name = f"audio/{scene.scene_id.lower()}-{scene.text_sha256[:12]}.wav"
        data = renderer.render(scene)
        path = workspace / name
        if path.is_file() and path.read_bytes() == data:
            reused += 1
        else:
            atomic_write_bytes(path, data)
            rendered += 1
        audio_names.append(name)
    playlist = "#EXTM3U\n" + "".join(f"#EXTINF:0.18,{name}\n{name}\n" for name in audio_names)
    atomic_write_text(workspace / "audiobook.m3u8", playlist)
    translated = (workspace / "translation.md").read_text(encoding="utf-8")
    chapters = split_speech_chapters(translated)
    manifest = {
        "schema_version": "potter-showcase-audiobook-v1",
        "audio_kind": "synthetic-tones-not-speech",
        "chapter_count": len(chapters),
        "scene_count": len(rows),
        "audio_files": audio_names,
        "rendered_now": rendered,
        "reused_now": reused,
    }
    atomic_write_json(workspace / "audiobook.json", manifest)
    return [*audio_names, "audiobook.m3u8", "audiobook.json"], manifest


RUNNERS = {
    Stage.IMPORT: _run_import,
    Stage.TRANSLATE: _run_translate,
    Stage.VERIFY: _run_verify,
    Stage.CAST: _run_cast,
    Stage.AUDIO_PLAN: _run_audio_plan,
    Stage.RENDER: _run_render,
}


def _detail(stage: Stage, details: dict[str, Any]) -> str:
    if stage is Stage.IMPORT:
        return f"{details['paragraphs']} абзацев; исходник зафиксирован"
    if stage is Stage.TRANSLATE:
        return f"{details['paragraphs']} абзацев; сетевых вызовов: 0"
    if stage is Stage.VERIFY:
        return "ID и исходный SHA-256 сохранены; структурных ошибок: 0"
    if stage is Stage.CAST:
        return f"{details['lines']} строк; ролей: {len(details['roles'])}"
    if stage is Stage.AUDIO_PLAN:
        return f"{details['scenes']} сцен; голосов: {details['voices']}"
    return (
        f"WAV: {len(details['audio_files'])}; создано: {details['rendered_now']}; "
        f"повторно использовано: {details['reused_now']}"
    )


def run_showcase(
    workspace: Path,
    *,
    stop_after: Stage | str | None = None,
    fail_before: Stage | str | None = None,
) -> PipelineSummary:
    """Execute or resume every public stage without network or private code."""
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    status_file = workspace / "pipeline.json"
    stop = Stage(stop_after) if stop_after is not None else None
    failure = Stage(fail_before) if fail_before is not None else None
    events: list[PipelineEvent] = []
    with exclusive_run(workspace / ".pipeline.lock"):
        state = _load_state(status_file)
        state["status"] = "running"
        atomic_write_json(status_file, state)
        try:
            for stage in STAGE_ORDER:
                if stage is failure:
                    raise DemoAdapterError(f"Контролируемый отказ перед этапом {stage.value}.")
                existing = state["completed"].get(stage.value)
                if existing is not None:
                    _validate_artifacts(workspace, existing)
                    artifact_count = len(existing["artifacts"])
                    events.append(
                        PipelineEvent(
                            stage,
                            "reused",
                            f"checkpoint проверен; артефактов: {artifact_count}",
                        )
                    )
                else:
                    names, details = RUNNERS[stage](workspace)
                    record = {
                        "artifacts": _artifact_hashes(workspace, names),
                        "details": details,
                    }
                    state["completed"][stage.value] = record
                    state["last_stage"] = stage.value
                    atomic_write_json(status_file, state)
                    events.append(PipelineEvent(stage, "completed", _detail(stage, details)))
                if stage is stop:
                    state["status"] = "paused"
                    state["last_stage"] = stage.value
                    atomic_write_json(status_file, state)
                    raise DemoInterrupted(
                        f"Демонстрация остановлена после {stage.value}; checkpoint сохранён."
                    )
            state["status"] = "completed"
            state["last_stage"] = Stage.RENDER.value
            state.pop("error_type", None)
            state.pop("error", None)
            atomic_write_json(status_file, state)
        except DemoInterrupted:
            raise
        except Exception as exc:
            state["status"] = "blocked"
            state["error_type"] = type(exc).__name__
            state["error"] = str(exc)
            atomic_write_json(status_file, state)
            raise
    book = _read_json(workspace / "audiobook.json")
    return PipelineSummary(
        workspace=workspace,
        events=tuple(events),
        chapter_count=int(book["chapter_count"]),
        scene_count=int(book["scene_count"]),
        audio_files=tuple(workspace / name for name in book["audio_files"]),
        status_file=status_file,
    )
