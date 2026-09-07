"""Audit and reproducibly package only the allowlisted public code tree."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
IGNORED = {".git", "__pycache__", ".pytest_cache", ".test-tmp", "demo-output", "dist"}
FORBIDDEN_SUFFIXES = {
    ".db", ".dll", ".docx", ".eml", ".epub", ".exe", ".flac", ".key",
    ".log", ".mp3", ".pdf", ".pem", ".sqlite", ".wav", ".zip",
}
LOCAL_PACKAGES = {"aitran", "tools"}
PLATFORM_STDLIB = {"fcntl", "msvcrt"}
MEDIA_SUFFIXES = {".gif", ".png"}
MAX_MEDIA_BYTES = 2_000_000
PRIVATE_MODULES = {
    "aitran.audiobook",
    "aitran.book_import",
    "aitran.book_markup",
    "aitran.book_pipeline",
    "aitran.cast_reader",
    "aitran.cast_scout",
    "aitran.config",
    "aitran.desktop",
    "aitran.graph",
    "aitran.llm",
    "aitran.prompting",
    "aitran.reader",
    "aitran.request_journal",
    "aitran.runner",
    "aitran.speech",
    "aitran.speech_repair",
    "aitran.storage",
    "aitran.story_memory",
}
FORBIDDEN_TEXT = {
    "deepseek" + "_api_key",
    "openrouter" + "_api_key",
    "c:" + "\\potter",
    "c:" + "/potter",
    "c:" + "\\aitran",
    "c:" + "/aitran",
    "c:" + "\\aibookgithub",
    "c:" + "/aibookgithub",
}


def _manifest(root: Path) -> list[str]:
    try:
        value = json.loads((root / "public-files.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("public-files.json is missing or invalid") from exc
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError("public manifest must be a JSON string list")
    if value != sorted(value) or len(value) != len(set(value)):
        raise ValueError("public manifest must be sorted and unique")
    return value


def _check_manifest_path(root: Path, name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
        raise ValueError(f"unsafe manifest path: {name}")
    if (
        any(part in IGNORED or part in {"output", "logs", "models", "notes"} for part in path.parts)
        or path.name.startswith(".env")
        or path.suffix.casefold() in FORBIDDEN_SUFFIXES
    ):
        raise ValueError(f"forbidden public file: {name}")
    target = root / name
    if not target.is_file() or target.is_symlink() or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"missing or unsafe public file: {name}")


def _actual_files(root: Path) -> set[str]:
    actual: set[str] = set()
    for file in root.rglob("*"):
        relative = file.relative_to(root)
        if any(part in IGNORED for part in relative.parts):
            continue
        if file.is_symlink():
            raise ValueError(f"symlink in public tree: {relative}")
        if file.is_file():
            actual.add(relative.as_posix())
    return actual


def _check_text(name: str, text: str) -> None:
    lowered = text.casefold()
    for marker in FORBIDDEN_TEXT:
        if marker in lowered:
            raise ValueError(f"obsolete path or private configuration marker: {name}")
    if re.search(r"(?i)\b[a-z]:[\\/]", text):
        raise ValueError(f"absolute drive path: {name}")
    if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", text):
        raise ValueError(f"private key marker: {name}")
    if re.search(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,})\b", text):
        raise ValueError(f"token-like string: {name}")


def _check_media(name: str, data: bytes) -> None:
    path = PurePosixPath(name)
    if path.parts[:2] != ("docs", "assets"):
        raise ValueError(f"media outside docs/assets: {name}")
    if len(data) > MAX_MEDIA_BYTES:
        raise ValueError(f"media file is too large: {name}")
    if path.suffix.casefold() == ".png":
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"invalid PNG header: {name}")
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
    else:
        if len(data) < 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
            raise ValueError(f"invalid GIF header: {name}")
        width = int.from_bytes(data[6:8], "little")
        height = int.from_bytes(data[8:10], "little")
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ValueError(f"invalid media dimensions: {name}")


def _check_imports(root: Path, name: str, text: str) -> None:
    tree = ast.parse(text, filename=name)
    for node in ast.walk(tree):
        modules = (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module] if isinstance(node, ast.ImportFrom) and node.module else []
        )
        for module in modules:
            if any(module == private or module.startswith(private + ".") for private in PRIVATE_MODULES):
                raise ValueError(f"private module import: {name}:{module}")
            top = module.split(".")[0]
            if top in LOCAL_PACKAGES:
                relative = module.replace(".", "/")
                if not (root / (relative + ".py")).is_file() and not (root / relative).is_dir():
                    raise ValueError(f"missing local import: {name}:{module}")
            elif top not in sys.stdlib_module_names and top not in PLATFORM_STDLIB:
                raise ValueError(f"unreviewed external import: {name}:{module}")


def audit(root: Path = ROOT) -> list[str]:
    files = _manifest(root)
    for name in files:
        _check_manifest_path(root, name)
    actual = _actual_files(root)
    if actual != set(files):
        raise ValueError(f"unlisted or missing public files: {sorted(actual.symmetric_difference(files))}")
    for name in files:
        path = root / name
        if path.suffix.casefold() in MEDIA_SUFFIXES:
            _check_media(name, path.read_bytes())
            continue
        if path.suffix.casefold() not in {".md", ".py", ".toml", ".json", ".yml", ""}:
            continue
        text = path.read_text(encoding="utf-8")
        _check_text(name, text)
        if name.endswith(".py"):
            _check_imports(root, name, text)
    provenance = json.loads((root / "provenance.json").read_text(encoding="utf-8"))
    if not isinstance(provenance, dict) or not provenance:
        raise ValueError("provenance.json must pin original files")
    for name, expected in provenance.items():
        if name not in files:
            raise ValueError(f"provenance file is not public: {name}")
        actual_hash = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if actual_hash != expected:
            raise ValueError(f"original source drift: {name}")
    return files


def build(files: list[str]) -> Path:
    destination = ROOT / "dist" / "book-to-audiobook-ai-showcase.zip"
    destination.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (ROOT / name).read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None or archive.namelist() != files:
            raise ValueError("ZIP verification failed")
        for name in files:
            if archive.read(name) != (ROOT / name).read_bytes():
                raise ValueError(f"ZIP content mismatch: {name}")
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(".zip.sha256").write_text(
        f"{digest}  {destination.name}\n", encoding="utf-8"
    )
    print(f"Built {destination.name}: {len(files)} files, SHA256 {digest}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--build", action="store_true")
    args = parser.parse_args()
    selected = audit()
    print(f"PUBLIC CHECK PASSED: {len(selected)} allowlisted files")
    if args.build:
        build(selected)
