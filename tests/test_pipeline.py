"""Executable scenario, recovery, and isolation regressions."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from aitran.contracts import TextDocument
from aitran.errors import DemoAdapterError, DemoInterrupted, WorkspaceConflictError
from aitran.showcase.adapters import FixtureTranslator
from aitran.showcase.fixtures import SOURCE_BOOK, SOURCE_SHA256
from aitran.showcase.models import Stage
from aitran.showcase.pipeline import run_showcase


class PipelineTests(unittest.TestCase):
    def workspace(self) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="book-audio-showcase-test-")
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_full_run_creates_real_derived_artifacts(self):
        workspace = self.workspace()
        summary = run_showcase(workspace)
        self.assertEqual(summary.chapter_count, 2)
        self.assertEqual(summary.scene_count, 8)
        self.assertEqual(len(summary.audio_files), 8)
        self.assertTrue(all(path.read_bytes().startswith(b"RIFF") for path in summary.audio_files))
        self.assertEqual((workspace / "source.md").read_text(encoding="utf-8"), SOURCE_BOOK)
        self.assertEqual(hashlib.sha256(SOURCE_BOOK.encode()).hexdigest(), SOURCE_SHA256)
        state = json.loads(summary.status_file.read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "completed")
        self.assertEqual(set(state["completed"]), {stage.value for stage in Stage})

    def test_second_run_validates_and_reuses_every_stage(self):
        workspace = self.workspace()
        first = run_showcase(workspace)
        hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in first.audio_files]
        second = run_showcase(workspace)
        self.assertTrue(all(event.action == "reused" for event in second.events))
        self.assertTrue(all("checkpoint проверен" in event.detail for event in second.events))
        self.assertEqual(hashes, [hashlib.sha256(path.read_bytes()).hexdigest() for path in second.audio_files])

    def test_interruption_resumes_from_saved_checkpoint(self):
        workspace = self.workspace()
        with self.assertRaises(DemoInterrupted):
            run_showcase(workspace, stop_after=Stage.TRANSLATE)
        paused = json.loads((workspace / "pipeline.json").read_text(encoding="utf-8"))
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(set(paused["completed"]), {"import", "translate"})
        resumed = run_showcase(workspace)
        self.assertEqual([event.action for event in resumed.events[:2]], ["reused", "reused"])
        self.assertTrue(all(event.action == "completed" for event in resumed.events[2:]))

    def test_controlled_failure_preserves_completed_work(self):
        workspace = self.workspace()
        with self.assertRaises(DemoAdapterError):
            run_showcase(workspace, fail_before=Stage.RENDER)
        blocked = json.loads((workspace / "pipeline.json").read_text(encoding="utf-8"))
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["error_type"], "DemoAdapterError")
        self.assertIn("render", blocked["error"])
        self.assertNotIn("render", blocked["completed"])
        resumed = run_showcase(workspace)
        self.assertEqual(resumed.events[-1].action, "completed")
        completed = json.loads(resumed.status_file.read_text(encoding="utf-8"))
        self.assertEqual(completed["status"], "completed")
        self.assertNotIn("error_type", completed)
        self.assertNotIn("error", completed)

    def test_changed_checkpoint_artifact_is_rejected(self):
        workspace = self.workspace()
        run_showcase(workspace)
        (workspace / "translation.md").write_text("tampered", encoding="utf-8")
        with self.assertRaises(WorkspaceConflictError):
            run_showcase(workspace)

    def test_fixture_translator_refuses_unknown_book(self):
        document = TextDocument.from_text("An unknown book.")
        with self.assertRaises(DemoAdapterError):
            FixtureTranslator().translate(document)

    def test_full_scenario_does_not_need_network(self):
        workspace = self.workspace()
        with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")):
            summary = run_showcase(workspace)
        self.assertEqual(len(summary.audio_files), 8)

    def test_playlist_references_only_created_audio(self):
        workspace = self.workspace()
        summary = run_showcase(workspace)
        playlist = (workspace / "audiobook.m3u8").read_text(encoding="utf-8")
        for path in summary.audio_files:
            self.assertIn(path.relative_to(summary.workspace).as_posix(), playlist)

    def test_cli_tour_uses_utf8_with_legacy_console_encoding(self):
        script = Path(__file__).resolve().parents[1] / "demo.py"
        result = subprocess.run(
            [sys.executable, str(script), "--tour"],
            env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", errors="replace"))
        output = result.stdout.decode("utf-8")
        self.assertIn("Демонстрация остановлена после translate", output)
        self.assertIn("READY · chapters=2 scenes=8 audio_files=8", output)


if __name__ == "__main__":
    unittest.main()
