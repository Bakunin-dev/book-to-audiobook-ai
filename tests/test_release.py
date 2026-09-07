"""Publication gate regressions."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.release import audit


class ReleaseTests(unittest.TestCase):
    def public_copy(self) -> Path:
        root = Path(__file__).resolve().parents[1]
        temporary = tempfile.TemporaryDirectory(prefix="potter-public-test-")
        self.addCleanup(temporary.cleanup)
        target_root = Path(temporary.name)
        for name in json.loads((root / "public-files.json").read_text(encoding="utf-8")):
            target = target_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
        return target_root

    def test_current_public_tree_passes(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit(root), sorted(audit(root)))

    def test_unlisted_file_is_rejected(self):
        root = self.public_copy()
        (root / "private.txt").write_text("not for publication", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "unlisted"):
            audit(root)

    def test_manifest_cannot_authorize_environment_file(self):
        root = self.public_copy()
        manifest = root / "public-files.json"
        files = json.loads(manifest.read_text(encoding="utf-8"))
        manifest.write_text(json.dumps(sorted([*files, ".env"])), encoding="utf-8")
        (root / ".env").write_text("SECRET=value", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "forbidden"):
            audit(root)

    def test_original_source_drift_is_rejected(self):
        root = self.public_copy()
        target = root / "aitran" / "contracts.py"
        target.write_text(target.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "original source drift"):
            audit(root)

    def test_absolute_drive_path_is_rejected(self):
        root = self.public_copy()
        target = root / "README.md"
        obsolete = "c:" + "\\old-installation"
        target.write_text(target.read_text(encoding="utf-8") + obsolete, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "absolute drive path"):
            audit(root)

    def test_private_module_import_is_rejected(self):
        root = self.public_copy()
        target = root / "aitran" / "showcase" / "adapters.py"
        target.write_text(target.read_text(encoding="utf-8") + "\nimport aitran.llm\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "private module import"):
            audit(root)

    def test_invalid_public_image_is_rejected(self):
        root = self.public_copy()
        target = root / "docs" / "assets" / "potter-cover.png"
        target.write_bytes(b"not a png")
        with self.assertRaisesRegex(ValueError, "invalid PNG header"):
            audit(root)

    def test_oversized_public_media_is_rejected(self):
        root = self.public_copy()
        target = root / "docs" / "assets" / "potter-cover.png"
        target.write_bytes(target.read_bytes() + b"0" * 2_000_000)
        with self.assertRaisesRegex(ValueError, "too large"):
            audit(root)


if __name__ == "__main__":
    unittest.main()
