# AI Slop Cleaner CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the CLI-first AI Slop Cleaner v1 that classifies project documents, writes a manifest, plans quarantine moves, applies safe moves, and restores quarantined files.

**Architecture:** The core package owns scanning, classification, manifest writing, and quarantine behavior. The CLI is a thin adapter over the core API, so a future MCP server can call the same functions without copying logic. The implementation is deterministic and offline.

**Tech Stack:** Python 3.12, `uv`, stdlib `argparse`, stdlib `dataclasses`, stdlib `json`, stdlib `pathlib`, stdlib `hashlib`, stdlib `re`, `pytest`.

---

## File Structure

Create these files:

- `pyproject.toml`: package metadata, console script, pytest config.
- `README.md`: CLI usage and agent timing contract.
- `src/ai_slop_cleaner/__init__.py`: package version.
- `src/ai_slop_cleaner/models.py`: shared dataclasses and constants.
- `src/ai_slop_cleaner/text_utils.py`: text normalization, frontmatter, title, headings, references, generated-noise helpers.
- `src/ai_slop_cleaner/scanner.py`: directory traversal and document fact extraction.
- `src/ai_slop_cleaner/classifier.py`: deterministic category assignment.
- `src/ai_slop_cleaner/manifest_writer.py`: manifest dict creation and JSON writing.
- `src/ai_slop_cleaner/core.py`: public core functions used by CLI and future MCP.
- `src/ai_slop_cleaner/quarantine.py`: cleanup planning, apply, and restore.
- `src/ai_slop_cleaner/cli.py`: CLI commands.
- `tests/test_cli_smoke.py`: package and help smoke tests.
- `tests/test_scanner.py`: scanner behavior tests.
- `tests/test_manifest_and_duplicates.py`: duplicate and manifest contract tests.
- `tests/test_classification_rules.py`: stale, conflict, and low-value tests.
- `tests/test_manifest_freshness.py`: usage timing and stale manifest tests.
- `tests/test_quarantine.py`: plan, apply, and restore tests.
- `tests/test_cli_integration.py`: end-to-end CLI behavior.

Do not create MCP server files in this plan. MCP is represented by the stable core API in `core.py`.

---

### Task 1: Package Scaffold And CLI Smoke

**Files:**
- Create: `pyproject.toml`
- Create: `README.md`
- Create: `src/ai_slop_cleaner/__init__.py`
- Create: `src/ai_slop_cleaner/cli.py`
- Create: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write the failing CLI smoke test**

```python
# tests/test_cli_smoke.py
from __future__ import annotations

import subprocess
import sys


def test_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ai_slop_cleaner.cli", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "AI Slop Cleaner" in result.stdout
    assert "classify" in result.stdout
    assert "clean" in result.stdout
    assert "restore" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --with pytest pytest tests/test_cli_smoke.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_slop_cleaner'`.

- [ ] **Step 3: Create the package scaffold**

```toml
# pyproject.toml
[project]
name = "ai-slop-cleaner"
version = "0.1.0"
description = "Deterministic document classification and quarantine for agent context hygiene."
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[project.scripts]
ai-slop = "ai_slop_cleaner.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.2",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

````markdown
# AI Slop Cleaner

AI Slop Cleaner is a CLI-first context hygiene tool for coding agents.

Agents should run `ai-slop classify <path>` before reading a project folder. If files change after the manifest timestamp, the agent should rerun classification before deciding what to read.

Initial commands:

```bash
ai-slop classify <path>
ai-slop clean --plan <path>
ai-slop clean --apply <path>
ai-slop restore <quarantine-run-path>
```

Version 1 is deterministic and offline. It does not delete files and does not call external LLM or embedding APIs.
````

```python
# src/ai_slop_cleaner/__init__.py
__version__ = "0.1.0"
```

```python
# src/ai_slop_cleaner/cli.py
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-slop",
        description="AI Slop Cleaner: deterministic document classification and quarantine.",
    )
    subparsers = parser.add_subparsers(dest="command")

    classify = subparsers.add_parser("classify", help="Scan a folder and write ai-slop-manifest.json.")
    classify.add_argument("path", help="Folder to classify.")

    clean = subparsers.add_parser("clean", help="Plan or apply quarantine moves.")
    clean_mode = clean.add_mutually_exclusive_group(required=True)
    clean_mode.add_argument("--plan", action="store_true", help="Write a cleanup plan without moving files.")
    clean_mode.add_argument("--apply", action="store_true", help="Move eligible files into quarantine.")
    clean.add_argument("path", help="Folder to clean.")

    restore = subparsers.add_parser("restore", help="Restore files from one quarantine run.")
    restore.add_argument("quarantine_run_path", help="Path to .ai-slop/quarantine/<timestamp>.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    parser.error("command implementation is not wired yet")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_cli_smoke.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md src/ai_slop_cleaner/__init__.py src/ai_slop_cleaner/cli.py tests/test_cli_smoke.py
git commit -m "chore: scaffold ai slop cleaner package"
```

---

### Task 2: Scanner Extracts Document Facts

**Files:**
- Create: `src/ai_slop_cleaner/models.py`
- Create: `src/ai_slop_cleaner/text_utils.py`
- Create: `src/ai_slop_cleaner/scanner.py`
- Create: `tests/test_scanner.py`

- [ ] **Step 1: Write failing scanner tests**

```python
# tests/test_scanner.py
from __future__ import annotations

from pathlib import Path

from ai_slop_cleaner.scanner import scan_documents


def test_scanner_extracts_markdown_facts(tmp_path: Path) -> None:
    doc = tmp_path / "spec.md"
    doc.write_text(
        "---\n"
        "title: Payment Spec\n"
        "status: canonical\n"
        "---\n"
        "# Payment Spec\n"
        "See [API](api.md) and [[notes]].\n",
        encoding="utf-8",
    )

    records = scan_documents(tmp_path)

    assert len(records) == 1
    record = records[0]
    assert record.relative_path == "spec.md"
    assert record.hash is not None
    assert record.size > 0
    assert record.extension == ".md"
    assert record.title == "Payment Spec"
    assert record.frontmatter == {"title": "Payment Spec", "status": "canonical"}
    assert record.headings == ["Payment Spec"]
    assert sorted(record.references) == ["api.md", "notes"]
    assert record.errors == []


def test_scanner_skips_internal_ai_slop_folder(tmp_path: Path) -> None:
    (tmp_path / ".ai-slop").mkdir()
    (tmp_path / ".ai-slop" / "old.md").write_text("internal", encoding="utf-8")
    (tmp_path / "live.md").write_text("# Live\n", encoding="utf-8")

    records = scan_documents(tmp_path)

    assert [record.relative_path for record in records] == ["live.md"]


def test_scanner_marks_binary_as_needs_review_input(tmp_path: Path) -> None:
    binary = tmp_path / "image.png"
    binary.write_bytes(b"\x89PNG\x00\x00\x00")

    records = scan_documents(tmp_path)

    assert len(records) == 1
    assert records[0].relative_path == "image.png"
    assert records[0].errors == ["binary_file"]
    assert records[0].normalized_text == ""


def test_scanner_marks_oversized_file(tmp_path: Path) -> None:
    big = tmp_path / "large.md"
    big.write_text("x" * 32, encoding="utf-8")

    records = scan_documents(tmp_path, max_bytes=16)

    assert len(records) == 1
    assert records[0].errors == ["oversized_file"]
    assert records[0].normalized_text == ""
```

- [ ] **Step 2: Run the scanner tests to verify they fail**

Run: `uv run pytest tests/test_scanner.py -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `ai_slop_cleaner.scanner`.

- [ ] **Step 3: Add shared models**

```python
# src/ai_slop_cleaner/models.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Category = Literal["canonical", "duplicate", "stale", "conflict", "low_value", "needs_review"]

CATEGORIES: tuple[Category, ...] = (
    "canonical",
    "duplicate",
    "stale",
    "conflict",
    "low_value",
    "needs_review",
)

MOVABLE_CATEGORIES: frozenset[Category] = frozenset({"duplicate", "stale", "low_value"})
MANIFEST_NAME = "ai-slop-manifest.json"


@dataclass(frozen=True)
class DocumentRecord:
    relative_path: str
    absolute_path: str
    hash: str | None
    size: int
    mtime: float
    extension: str
    title: str | None
    frontmatter: dict[str, str]
    normalized_text: str
    headings: list[str]
    references: list[str]
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClassificationResult:
    path: str
    category: Category
    confidence: float
    signals: list[dict[str, Any]]
    reason: str
    related_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_manifest_entry(self, record: DocumentRecord) -> dict[str, Any]:
        entry = asdict(self)
        entry.update(
            {
                "hash": record.hash,
                "size": record.size,
                "mtime": record.mtime,
                "title": record.title,
                "extension": record.extension,
            }
        )
        return entry
```

- [ ] **Step 4: Add text utilities**

```python
# src/ai_slop_cleaner/text_utils.py
from __future__ import annotations

import re

FRONTMATTER_BOUNDARY = "---"


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"```.*?```", " ", lowered, flags=re.DOTALL)
    lowered = re.sub(r"[^\w\s-]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_BOUNDARY:
        return {}, text

    frontmatter: dict[str, str] = {}
    body_start = 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_BOUNDARY:
            body_start = index + 1
            break
        if ":" in line:
            key, value = line.split(":", 1)
            clean_key = key.strip()
            clean_value = value.strip().strip("\"'")
            if clean_key:
                frontmatter[clean_key] = clean_value

    if body_start == 0:
        return {}, text
    return frontmatter, "\n".join(lines[body_start:])


def extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def extract_title(frontmatter: dict[str, str], text: str) -> str | None:
    if frontmatter.get("title"):
        return frontmatter["title"]
    headings = extract_headings(text)
    if headings:
        return headings[0]
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return None


def extract_references(text: str) -> list[str]:
    markdown_refs = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    wiki_refs = re.findall(r"\[\[([^\]]+)\]\]", text)
    refs = [ref.strip() for ref in markdown_refs + wiki_refs if ref.strip()]
    return sorted(set(refs))


def is_binary_bytes(raw: bytes) -> bool:
    return b"\x00" in raw
```

- [ ] **Step 5: Add scanner implementation**

```python
# src/ai_slop_cleaner/scanner.py
from __future__ import annotations

import hashlib
from pathlib import Path

from ai_slop_cleaner.models import MANIFEST_NAME, DocumentRecord
from ai_slop_cleaner.text_utils import (
    extract_headings,
    extract_references,
    extract_title,
    is_binary_bytes,
    normalize_text,
    split_frontmatter,
)

IGNORE_DIRS = {".git", ".hg", ".svn", ".ai-slop", "__pycache__", ".pytest_cache", ".mypy_cache"}


def scan_documents(target: str | Path, *, max_bytes: int = 1_000_000) -> list[DocumentRecord]:
    root = Path(target).resolve()
    records: list[DocumentRecord] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _is_ignored(path, root):
            continue
        records.append(_scan_file(path, root, max_bytes=max_bytes))

    return records


def _is_ignored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if path.name == MANIFEST_NAME:
        return True
    return any(part in IGNORE_DIRS for part in relative.parts)


def _scan_file(path: Path, root: Path, *, max_bytes: int) -> DocumentRecord:
    stat = path.stat()
    relative_path = path.relative_to(root).as_posix()
    file_hash = _hash_file(path)
    extension = path.suffix.lower()

    if stat.st_size > max_bytes:
        return DocumentRecord(
            relative_path=relative_path,
            absolute_path=str(path),
            hash=file_hash,
            size=stat.st_size,
            mtime=stat.st_mtime,
            extension=extension,
            title=None,
            frontmatter={},
            normalized_text="",
            headings=[],
            references=[],
            errors=["oversized_file"],
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _error_record(path, root, file_hash, stat.st_size, stat.st_mtime, extension, f"read_error:{exc.__class__.__name__}")

    if is_binary_bytes(raw):
        return _error_record(path, root, file_hash, stat.st_size, stat.st_mtime, extension, "binary_file")

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return _error_record(path, root, file_hash, stat.st_size, stat.st_mtime, extension, "decode_error")

    frontmatter, body = split_frontmatter(text)
    title = extract_title(frontmatter, body)

    return DocumentRecord(
        relative_path=relative_path,
        absolute_path=str(path),
        hash=file_hash,
        size=stat.st_size,
        mtime=stat.st_mtime,
        extension=extension,
        title=title,
        frontmatter=frontmatter,
        normalized_text=normalize_text(body),
        headings=extract_headings(body),
        references=extract_references(body),
        errors=[],
    )


def _error_record(
    path: Path,
    root: Path,
    file_hash: str | None,
    size: int,
    mtime: float,
    extension: str,
    error: str,
) -> DocumentRecord:
    return DocumentRecord(
        relative_path=path.relative_to(root).as_posix(),
        absolute_path=str(path),
        hash=file_hash,
        size=size,
        mtime=mtime,
        extension=extension,
        title=None,
        frontmatter={},
        normalized_text="",
        headings=[],
        references=[],
        errors=[error],
    )


def _hash_file(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()
```

- [ ] **Step 6: Run scanner tests**

Run: `uv run pytest tests/test_scanner.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/ai_slop_cleaner/models.py src/ai_slop_cleaner/text_utils.py src/ai_slop_cleaner/scanner.py tests/test_scanner.py
git commit -m "feat: scan documents"
```

---

### Task 3: Duplicate Classification And Manifest Contract

**Files:**
- Create: `src/ai_slop_cleaner/classifier.py`
- Create: `src/ai_slop_cleaner/manifest_writer.py`
- Create: `tests/test_manifest_and_duplicates.py`

- [ ] **Step 1: Write failing duplicate and manifest tests**

```python
# tests/test_manifest_and_duplicates.py
from __future__ import annotations

from pathlib import Path

from ai_slop_cleaner.classifier import classify_records
from ai_slop_cleaner.manifest_writer import build_manifest
from ai_slop_cleaner.scanner import scan_documents


def test_same_content_different_names_becomes_duplicate(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame content.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame content.\n", encoding="utf-8")

    records = scan_documents(tmp_path)
    results = classify_records(records)

    categories = {result.path: result.category for result in results}
    assert sorted(categories.values()) == ["canonical", "duplicate"]
    duplicate = next(result for result in results if result.category == "duplicate")
    assert duplicate.confidence == 0.99
    assert duplicate.signals[0]["name"] == "exact_hash_duplicate"


def test_manifest_has_category_buckets_and_file_entries(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame content.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame content.\n", encoding="utf-8")

    records = scan_documents(tmp_path)
    results = classify_records(records)
    manifest = build_manifest(tmp_path, records, results, scanner_config={"max_bytes": 1_000_000})

    assert manifest["schema_version"] == 1
    assert manifest["target_path"] == str(tmp_path.resolve())
    assert sorted(manifest["categories"]) == ["canonical", "conflict", "duplicate", "low_value", "needs_review", "stale"]
    assert len(manifest["files"]) == 2
    assert len(manifest["categories"]["canonical"]) == 1
    assert len(manifest["categories"]["duplicate"]) == 1
    assert manifest["files"][0]["reason"]
    assert "signals" in manifest["files"][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_manifest_and_duplicates.py -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `classifier` or `manifest_writer`.

- [ ] **Step 3: Add initial classifier**

```python
# src/ai_slop_cleaner/classifier.py
from __future__ import annotations

from collections import defaultdict

from ai_slop_cleaner.models import ClassificationResult, DocumentRecord


def classify_records(records: list[DocumentRecord]) -> list[ClassificationResult]:
    results: dict[str, ClassificationResult] = {}

    for record in records:
        if record.errors:
            results[record.relative_path] = ClassificationResult(
                path=record.relative_path,
                category="needs_review",
                confidence=1.0,
                signals=[{"name": "scanner_error", "value": record.errors}],
                reason="Scanner could not safely read this file.",
                errors=record.errors,
            )
        else:
            results[record.relative_path] = ClassificationResult(
                path=record.relative_path,
                category="canonical",
                confidence=0.6,
                signals=[{"name": "default_candidate", "value": True}],
                reason="No stale, duplicate, low-value, or conflict signal found.",
            )

    for group in _hash_groups(records):
        canonical = _choose_canonical(group)
        for record in group:
            if record.relative_path == canonical.relative_path:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="canonical",
                    confidence=0.95,
                    signals=[{"name": "duplicate_group_canonical", "value": True}],
                    reason="Selected as canonical representative for an exact duplicate group.",
                    related_files=[item.relative_path for item in group if item.relative_path != record.relative_path],
                )
            else:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="duplicate",
                    confidence=0.99,
                    signals=[{"name": "exact_hash_duplicate", "value": canonical.relative_path}],
                    reason=f"Content hash matches canonical file {canonical.relative_path}.",
                    related_files=[canonical.relative_path],
                )

    return [results[record.relative_path] for record in sorted(records, key=lambda item: item.relative_path)]


def _hash_groups(records: list[DocumentRecord]) -> list[list[DocumentRecord]]:
    groups: dict[str, list[DocumentRecord]] = defaultdict(list)
    for record in records:
        if record.hash and not record.errors:
            groups[record.hash].append(record)
    return [group for group in groups.values() if len(group) > 1]


def _choose_canonical(records: list[DocumentRecord]) -> DocumentRecord:
    return sorted(records, key=_canonical_sort_key, reverse=True)[0]


def _canonical_sort_key(record: DocumentRecord) -> tuple[int, int, float, int, str]:
    frontmatter_score = 0
    if record.frontmatter.get("canonical", "").lower() in {"true", "yes", "1"}:
        frontmatter_score += 4
    if record.frontmatter.get("status", "").lower() in {"canonical", "current", "final"}:
        frontmatter_score += 3
    filename_score = 1 if any(token in record.relative_path.lower() for token in ("final", "current", "latest")) else 0
    reference_score = len(record.references)
    return (frontmatter_score, filename_score, record.mtime, reference_score, record.relative_path)
```

- [ ] **Step 4: Add manifest writer**

```python
# src/ai_slop_cleaner/manifest_writer.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_slop_cleaner.models import CATEGORIES, MANIFEST_NAME, ClassificationResult, DocumentRecord


def build_manifest(
    target: str | Path,
    records: list[DocumentRecord],
    results: list[ClassificationResult],
    *,
    scanner_config: dict[str, Any],
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc)
    record_by_path = {record.relative_path: record for record in records}
    categories = {category: [] for category in CATEGORIES}
    files: list[dict[str, Any]] = []

    for result in sorted(results, key=lambda item: item.path):
        categories[result.category].append(result.path)
        files.append(result.to_manifest_entry(record_by_path[result.path]))

    return {
        "schema_version": 1,
        "target_path": str(Path(target).resolve()),
        "generated_at": generated_at.isoformat(),
        "generated_at_epoch": generated_at.timestamp(),
        "scanner_config": scanner_config,
        "categories": categories,
        "files": files,
    }


def write_manifest(target: str | Path, manifest: dict[str, Any]) -> Path:
    manifest_path = Path(target).resolve() / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path
```

- [ ] **Step 5: Run duplicate and manifest tests**

Run: `uv run pytest tests/test_manifest_and_duplicates.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_slop_cleaner/classifier.py src/ai_slop_cleaner/manifest_writer.py tests/test_manifest_and_duplicates.py
git commit -m "feat: classify exact duplicates and write manifest"
```

---

### Task 4: Stale, Low-Value, And Conflict Rules

**Files:**
- Modify: `src/ai_slop_cleaner/classifier.py`
- Create: `tests/test_classification_rules.py`

- [ ] **Step 1: Write failing classification rule tests**

```python
# tests/test_classification_rules.py
from __future__ import annotations

from pathlib import Path

from ai_slop_cleaner.classifier import classify_records
from ai_slop_cleaner.scanner import scan_documents


def _categories(tmp_path: Path) -> dict[str, str]:
    records = scan_documents(tmp_path)
    results = classify_records(records)
    return {result.path: result.category for result in results}


def test_newer_spec_supersedes_older_spec(tmp_path: Path) -> None:
    old = tmp_path / "payment-spec-v1.md"
    new = tmp_path / "payment-spec-v2.md"
    old.write_text("# Payment Spec\nThe API uses token auth.\n", encoding="utf-8")
    new.write_text("# Payment Spec\nThe API uses OAuth.\n", encoding="utf-8")
    old.touch()
    new.touch()

    categories = _categories(tmp_path)

    assert categories["payment-spec-v1.md"] == "stale"
    assert categories["payment-spec-v2.md"] == "canonical"


def test_generated_boilerplate_becomes_low_value(tmp_path: Path) -> None:
    (tmp_path / "summary.md").write_text(
        "# AI Summary\n"
        "This document summarizes the above content. It is a high-level overview generated by AI.\n",
        encoding="utf-8",
    )

    categories = _categories(tmp_path)

    assert categories["summary.md"] == "low_value"


def test_direct_requirement_conflict_is_flagged(tmp_path: Path) -> None:
    (tmp_path / "auth-a.md").write_text("# Auth\nThe product must support SSO.\n", encoding="utf-8")
    (tmp_path / "auth-b.md").write_text("# Auth\nThe product must not support SSO.\n", encoding="utf-8")

    categories = _categories(tmp_path)

    assert categories["auth-a.md"] == "conflict"
    assert categories["auth-b.md"] == "conflict"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_classification_rules.py -v`

Expected: FAIL because the current classifier only handles exact duplicates and scanner errors.

- [ ] **Step 3: Replace classifier with deterministic rule set**

```python
# src/ai_slop_cleaner/classifier.py
from __future__ import annotations

import re
from collections import defaultdict

from ai_slop_cleaner.models import ClassificationResult, DocumentRecord


def classify_records(records: list[DocumentRecord]) -> list[ClassificationResult]:
    results: dict[str, ClassificationResult] = _initial_results(records)

    for group in _hash_groups(records):
        canonical = _choose_canonical(group)
        for record in group:
            if record.relative_path == canonical.relative_path:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="canonical",
                    confidence=0.95,
                    signals=[{"name": "duplicate_group_canonical", "value": True}],
                    reason="Selected as canonical representative for an exact duplicate group.",
                    related_files=[item.relative_path for item in group if item.relative_path != record.relative_path],
                )
            else:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="duplicate",
                    confidence=0.99,
                    signals=[{"name": "exact_hash_duplicate", "value": canonical.relative_path}],
                    reason=f"Content hash matches canonical file {canonical.relative_path}.",
                    related_files=[canonical.relative_path],
                )

    _apply_low_value(records, results)
    _apply_conflicts(records, results)
    _apply_stale(records, results)

    return [results[record.relative_path] for record in sorted(records, key=lambda item: item.relative_path)]


def _initial_results(records: list[DocumentRecord]) -> dict[str, ClassificationResult]:
    results: dict[str, ClassificationResult] = {}
    for record in records:
        if record.errors:
            results[record.relative_path] = ClassificationResult(
                path=record.relative_path,
                category="needs_review",
                confidence=1.0,
                signals=[{"name": "scanner_error", "value": record.errors}],
                reason="Scanner could not safely read this file.",
                errors=record.errors,
            )
        else:
            results[record.relative_path] = ClassificationResult(
                path=record.relative_path,
                category="canonical",
                confidence=0.6,
                signals=[{"name": "default_candidate", "value": True}],
                reason="No stale, duplicate, low-value, or conflict signal found.",
            )
    return results


def _hash_groups(records: list[DocumentRecord]) -> list[list[DocumentRecord]]:
    groups: dict[str, list[DocumentRecord]] = defaultdict(list)
    for record in records:
        if record.hash and not record.errors:
            groups[record.hash].append(record)
    return [group for group in groups.values() if len(group) > 1]


def _apply_low_value(records: list[DocumentRecord], results: dict[str, ClassificationResult]) -> None:
    for record in records:
        if results[record.relative_path].category != "canonical":
            continue
        if _is_low_value(record):
            results[record.relative_path] = ClassificationResult(
                path=record.relative_path,
                category="low_value",
                confidence=0.82,
                signals=[{"name": "generated_noise_pattern", "value": True}],
                reason="File matches deterministic generated-summary or boilerplate patterns.",
            )


def _apply_conflicts(records: list[DocumentRecord], results: dict[str, ClassificationResult]) -> None:
    for group in _document_key_groups(records):
        active = [record for record in group if results[record.relative_path].category == "canonical"]
        if len(active) < 2:
            continue
        conflict_paths = _conflicting_paths(active)
        if not conflict_paths:
            continue
        for record in active:
            if record.relative_path in conflict_paths:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="conflict",
                    confidence=0.84,
                    signals=[{"name": "direct_requirement_conflict", "value": sorted(conflict_paths)}],
                    reason="A document with the same topic contains an opposite requirement statement.",
                    related_files=sorted(path for path in conflict_paths if path != record.relative_path),
                )


def _apply_stale(records: list[DocumentRecord], results: dict[str, ClassificationResult]) -> None:
    for group in _document_key_groups(records):
        active = [record for record in group if results[record.relative_path].category == "canonical"]
        if len(active) < 2:
            continue

        canonical = _choose_canonical(active)
        for record in active:
            if record.relative_path == canonical.relative_path:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="canonical",
                    confidence=0.86,
                    signals=[{"name": "topic_group_canonical", "value": _document_key(record)}],
                    reason="Selected as current file in a topic group.",
                    related_files=[item.relative_path for item in active if item.relative_path != record.relative_path],
                )
            elif _version_number(canonical) > _version_number(record) or canonical.mtime >= record.mtime:
                results[record.relative_path] = ClassificationResult(
                    path=record.relative_path,
                    category="stale",
                    confidence=0.83,
                    signals=[
                        {"name": "same_topic_as_newer_file", "value": canonical.relative_path},
                        {"name": "document_key", "value": _document_key(record)},
                    ],
                    reason=f"File appears superseded by {canonical.relative_path}.",
                    related_files=[canonical.relative_path],
                )


def _document_key_groups(records: list[DocumentRecord]) -> list[list[DocumentRecord]]:
    groups: dict[str, list[DocumentRecord]] = defaultdict(list)
    for record in records:
        if not record.errors:
            groups[_document_key(record)].append(record)
    return [group for group in groups.values() if len(group) > 1]


def _document_key(record: DocumentRecord) -> str:
    source = record.title or record.relative_path.rsplit("/", 1)[-1]
    source = source.lower()
    source = re.sub(r"\.[a-z0-9]+$", "", source)
    source = re.sub(r"\b(v|version)[-_ ]?\d+\b", "", source)
    source = re.sub(r"\b\d{4}[-_ ]?\d{2}[-_ ]?\d{2}\b", "", source)
    source = re.sub(r"\b(old|draft|copy|final|latest|current)\b", "", source)
    source = re.sub(r"[^a-z0-9]+", " ", source)
    return re.sub(r"\s+", " ", source).strip()


def _choose_canonical(records: list[DocumentRecord]) -> DocumentRecord:
    return sorted(records, key=_canonical_sort_key, reverse=True)[0]


def _canonical_sort_key(record: DocumentRecord) -> tuple[int, int, int, float, int, str]:
    frontmatter_score = 0
    if record.frontmatter.get("canonical", "").lower() in {"true", "yes", "1"}:
        frontmatter_score += 4
    if record.frontmatter.get("status", "").lower() in {"canonical", "current", "final"}:
        frontmatter_score += 3

    path_lower = record.relative_path.lower()
    filename_score = 0
    if any(token in path_lower for token in ("final", "current", "latest")):
        filename_score += 2
    if any(token in path_lower for token in ("old", "draft", "copy")):
        filename_score -= 2

    return (
        frontmatter_score,
        filename_score,
        _version_number(record),
        record.mtime,
        len(record.references),
        record.relative_path,
    )


def _version_number(record: DocumentRecord) -> int:
    text = f"{record.relative_path} {record.title or ''}".lower()
    matches = re.findall(r"\b(?:v|version)[-_ ]?(\d+)\b", text)
    if not matches:
        return 0
    return max(int(match) for match in matches)


def _is_low_value(record: DocumentRecord) -> bool:
    text = record.normalized_text
    title = (record.title or "").lower()
    token_count = len(text.split())
    generated_patterns = (
        "ai summary",
        "generated by ai",
        "summarizes the above content",
        "high level overview",
        "this document summarizes",
    )
    if any(pattern in title or pattern in text for pattern in generated_patterns):
        return True
    if token_count <= 3 and not record.title and not record.frontmatter:
        return True
    return False


def _conflicting_paths(records: list[DocumentRecord]) -> set[str]:
    claims: dict[tuple[str, str], dict[bool, set[str]]] = defaultdict(lambda: {True: set(), False: set()})
    for record in records:
        for claim in _extract_requirement_claims(record.normalized_text):
            claims[(claim["verb"], claim["object"])][claim["negated"]].add(record.relative_path)

    conflict_paths: set[str] = set()
    for polarity in claims.values():
        if polarity[True] and polarity[False]:
            conflict_paths.update(polarity[True])
            conflict_paths.update(polarity[False])
    return conflict_paths


def _extract_requirement_claims(text: str) -> list[dict[str, object]]:
    pattern = re.compile(
        r"\b(?:must|should|shall)\s+(?P<negated>not\s+)?"
        r"(?P<verb>support|include|use|require|allow|enable)\s+"
        r"(?P<object>[a-z0-9][a-z0-9 _-]{1,80})"
    )
    claims: list[dict[str, object]] = []
    for match in pattern.finditer(text):
        obj = re.sub(r"\s+", " ", match.group("object")).strip()
        claims.append(
            {
                "negated": bool(match.group("negated")),
                "verb": match.group("verb"),
                "object": obj,
            }
        )
    return claims
```

- [ ] **Step 4: Run classification rule tests**

Run: `uv run pytest tests/test_classification_rules.py -v`

Expected: PASS.

- [ ] **Step 5: Run existing duplicate tests**

Run: `uv run pytest tests/test_manifest_and_duplicates.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_slop_cleaner/classifier.py tests/test_classification_rules.py
git commit -m "feat: classify stale low value and conflict files"
```

---

### Task 5: Core API And Manifest Freshness

**Files:**
- Create: `src/ai_slop_cleaner/core.py`
- Create: `tests/test_manifest_freshness.py`

- [ ] **Step 1: Write failing freshness and core API tests**

```python
# tests/test_manifest_freshness.py
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from ai_slop_cleaner.core import StaleManifestError, classify_path, ensure_current_manifest, manifest_is_current
from ai_slop_cleaner.models import MANIFEST_NAME


def test_classify_path_writes_manifest(tmp_path: Path) -> None:
    (tmp_path / "spec.md").write_text("# Spec\nCurrent.\n", encoding="utf-8")

    manifest = classify_path(tmp_path)

    manifest_path = tmp_path / MANIFEST_NAME
    assert manifest_path.exists()
    assert manifest["categories"]["canonical"] == ["spec.md"]


def test_manifest_is_stale_when_file_changes_after_generation(tmp_path: Path) -> None:
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nCurrent.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    doc.write_text("# Spec\nChanged.\n", encoding="utf-8")
    os.utime(doc, (manifest["generated_at_epoch"] + 5, manifest["generated_at_epoch"] + 5))

    assert manifest_is_current(tmp_path, manifest) is False


def test_ensure_current_manifest_fails_when_stale(tmp_path: Path) -> None:
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nCurrent.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    doc.write_text("# Spec\nChanged.\n", encoding="utf-8")
    os.utime(doc, (manifest["generated_at_epoch"] + 5, manifest["generated_at_epoch"] + 5))

    with pytest.raises(StaleManifestError):
        ensure_current_manifest(tmp_path)


def test_ensure_current_manifest_rescans_when_requested(tmp_path: Path) -> None:
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nCurrent.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    doc.write_text("# Spec\nChanged.\n", encoding="utf-8")
    os.utime(doc, (manifest["generated_at_epoch"] + 5, manifest["generated_at_epoch"] + 5))

    manifest = ensure_current_manifest(tmp_path, rescan=True)

    assert json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))["generated_at"] == manifest["generated_at"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_manifest_freshness.py -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `core`.

- [ ] **Step 3: Add core API implementation**

```python
# src/ai_slop_cleaner/core.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_slop_cleaner.classifier import classify_records
from ai_slop_cleaner.manifest_writer import build_manifest, write_manifest
from ai_slop_cleaner.models import MANIFEST_NAME
from ai_slop_cleaner.scanner import scan_documents


class StaleManifestError(RuntimeError):
    pass


def classify_path(target: str | Path, *, write: bool = True, max_bytes: int = 1_000_000) -> dict[str, Any]:
    target_path = Path(target).resolve()
    records = scan_documents(target_path, max_bytes=max_bytes)
    results = classify_records(records)
    manifest = build_manifest(target_path, records, results, scanner_config={"max_bytes": max_bytes})
    if write:
        write_manifest(target_path, manifest)
    return manifest


def load_manifest(target: str | Path) -> dict[str, Any]:
    manifest_path = Path(target).resolve() / MANIFEST_NAME
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def manifest_is_current(target: str | Path, manifest: dict[str, Any]) -> bool:
    target_path = Path(target).resolve()
    generated_at_epoch = float(manifest["generated_at_epoch"])
    for path in target_path.rglob("*"):
        if not path.is_file():
            continue
        if _is_internal_or_manifest(path, target_path):
            continue
        if path.stat().st_mtime > generated_at_epoch:
            return False
    return True


def ensure_current_manifest(target: str | Path, *, rescan: bool = False) -> dict[str, Any]:
    target_path = Path(target).resolve()
    manifest_path = target_path / MANIFEST_NAME
    if not manifest_path.exists():
        if rescan:
            return classify_path(target_path)
        raise StaleManifestError(f"Manifest not found: {manifest_path}")

    manifest = load_manifest(target_path)
    if manifest_is_current(target_path, manifest):
        return manifest
    if rescan:
        return classify_path(target_path)
    raise StaleManifestError("Manifest is stale. Run classify again or pass --rescan.")


def _is_internal_or_manifest(path: Path, target: Path) -> bool:
    relative = path.relative_to(target)
    if path.name == MANIFEST_NAME:
        return True
    return ".ai-slop" in relative.parts
```

- [ ] **Step 4: Run freshness tests**

Run: `uv run pytest tests/test_manifest_freshness.py -v`

Expected: PASS.

- [ ] **Step 5: Run scanner, classification, and manifest tests**

Run: `uv run pytest tests/test_scanner.py tests/test_manifest_and_duplicates.py tests/test_classification_rules.py tests/test_manifest_freshness.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_slop_cleaner/core.py tests/test_manifest_freshness.py
git commit -m "feat: add core classification API and freshness checks"
```

---

### Task 6: Quarantine Plan, Apply, And Restore

**Files:**
- Create: `src/ai_slop_cleaner/quarantine.py`
- Create: `tests/test_quarantine.py`

- [ ] **Step 1: Write failing quarantine tests**

```python
# tests/test_quarantine.py
from __future__ import annotations

from pathlib import Path

from ai_slop_cleaner.core import classify_path
from ai_slop_cleaner.quarantine import apply_cleanup, plan_cleanup, restore_quarantine


def test_clean_plan_does_not_move_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    plan = plan_cleanup(tmp_path, manifest)

    assert len(plan["moves"]) == 1
    assert (tmp_path / "a.md").exists()
    assert (tmp_path / "b.md").exists()
    assert (tmp_path / ".ai-slop" / "cleanup-plan.json").exists()


def test_clean_apply_moves_only_eligible_categories(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    (tmp_path / "conflict-a.md").write_text("# Auth\nThe product must support SSO.\n", encoding="utf-8")
    (tmp_path / "conflict-b.md").write_text("# Auth\nThe product must not support SSO.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    run_path = apply_cleanup(tmp_path, manifest)

    assert run_path.exists()
    moved_files = list(run_path.rglob("*.md"))
    assert len(moved_files) == 1
    assert (tmp_path / "conflict-a.md").exists()
    assert (tmp_path / "conflict-b.md").exists()
    assert (run_path / "move-log.json").exists()
    assert (run_path / "manifest.json").exists()


def test_restore_moves_files_back_without_overwriting(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    cleanup_plan = plan_cleanup(tmp_path, manifest)
    moved_original = cleanup_plan["moves"][0]["original_path"]
    run_path = apply_cleanup(tmp_path, manifest)

    summary = restore_quarantine(run_path)

    assert summary["restored"] == [moved_original]
    assert summary["skipped"] == []
    assert (tmp_path / moved_original).exists()


def test_restore_skips_existing_destination(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    cleanup_plan = plan_cleanup(tmp_path, manifest)
    moved_original = cleanup_plan["moves"][0]["original_path"]
    run_path = apply_cleanup(tmp_path, manifest)
    (tmp_path / moved_original).write_text("new file", encoding="utf-8")

    summary = restore_quarantine(run_path)

    assert summary["restored"] == []
    assert summary["skipped"] == [{"path": moved_original, "reason": "destination_exists"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_quarantine.py -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `quarantine`.

- [ ] **Step 3: Add quarantine implementation**

```python
# src/ai_slop_cleaner/quarantine.py
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_slop_cleaner.models import MOVABLE_CATEGORIES


def plan_cleanup(target: str | Path, manifest: dict[str, Any], *, min_confidence: float = 0.75) -> dict[str, Any]:
    target_path = Path(target).resolve()
    created_at = datetime.now(timezone.utc)
    moves: list[dict[str, Any]] = []

    for entry in manifest["files"]:
        if entry["category"] not in MOVABLE_CATEGORIES:
            continue
        if float(entry["confidence"]) < min_confidence:
            continue
        source = target_path / entry["path"]
        if not source.exists():
            continue
        moves.append(
            {
                "original_path": entry["path"],
                "category": entry["category"],
                "confidence": entry["confidence"],
                "reason": entry["reason"],
            }
        )

    plan = {
        "created_at": created_at.isoformat(),
        "target_path": str(target_path),
        "min_confidence": min_confidence,
        "moves": sorted(moves, key=lambda item: item["original_path"]),
    }

    plan_dir = target_path / ".ai-slop"
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "cleanup-plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return plan


def apply_cleanup(target: str | Path, manifest: dict[str, Any], *, min_confidence: float = 0.75) -> Path:
    target_path = Path(target).resolve()
    plan = plan_cleanup(target_path, manifest, min_confidence=min_confidence)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_path = target_path / ".ai-slop" / "quarantine" / run_id
    run_path.mkdir(parents=True, exist_ok=False)

    move_log: list[dict[str, Any]] = []
    for move in plan["moves"]:
        source = target_path / move["original_path"]
        destination = run_path / move["original_path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        move_log.append(
            {
                **move,
                "quarantine_path": str(destination.relative_to(run_path)),
                "moved_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    (run_path / "move-log.json").write_text(json.dumps(move_log, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (run_path / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run_path


def restore_quarantine(quarantine_run_path: str | Path) -> dict[str, Any]:
    run_path = Path(quarantine_run_path).resolve()
    move_log = json.loads((run_path / "move-log.json").read_text(encoding="utf-8"))
    target_path = Path(json.loads((run_path / "manifest.json").read_text(encoding="utf-8"))["target_path"])
    restored: list[str] = []
    skipped: list[dict[str, str]] = []

    for move in move_log:
        original_path = move["original_path"]
        source = run_path / move["quarantine_path"]
        destination = target_path / original_path
        if destination.exists():
            skipped.append({"path": original_path, "reason": "destination_exists"})
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        restored.append(original_path)

    return {"restored": restored, "skipped": skipped}
```

- [ ] **Step 4: Run quarantine tests**

Run: `uv run pytest tests/test_quarantine.py -v`

Expected: PASS.

- [ ] **Step 5: Run classification and freshness regression tests**

Run: `uv run pytest tests/test_manifest_and_duplicates.py tests/test_classification_rules.py tests/test_manifest_freshness.py tests/test_quarantine.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_slop_cleaner/quarantine.py tests/test_quarantine.py
git commit -m "feat: quarantine and restore cleanup candidates"
```

---

### Task 7: Wire CLI Commands To Core Behavior

**Files:**
- Modify: `src/ai_slop_cleaner/cli.py`
- Create: `tests/test_cli_integration.py`

- [ ] **Step 1: Write failing CLI integration tests**

```python
# tests/test_cli_integration.py
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ai_slop_cleaner.models import MANIFEST_NAME


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ai_slop_cleaner.cli", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_classify_writes_manifest(tmp_path: Path) -> None:
    (tmp_path / "spec.md").write_text("# Spec\nCurrent.\n", encoding="utf-8")

    result = run_cli("classify", str(tmp_path))

    assert result.returncode == 0
    assert (tmp_path / MANIFEST_NAME).exists()
    payload = json.loads(result.stdout)
    assert payload["manifest_path"] == str(tmp_path / MANIFEST_NAME)
    assert payload["counts"]["canonical"] == 1


def test_cli_clean_plan_refuses_stale_manifest(tmp_path: Path) -> None:
    doc = tmp_path / "spec.md"
    doc.write_text("# Spec\nCurrent.\n", encoding="utf-8")
    assert run_cli("classify", str(tmp_path)).returncode == 0
    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    doc.write_text("# Spec\nChanged.\n", encoding="utf-8")
    os.utime(doc, (manifest["generated_at_epoch"] + 5, manifest["generated_at_epoch"] + 5))

    result = run_cli("clean", "--plan", str(tmp_path))

    assert result.returncode == 2
    assert "Manifest is stale" in result.stderr


def test_cli_clean_apply_and_restore(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Spec\nSame.\n", encoding="utf-8")
    assert run_cli("classify", str(tmp_path)).returncode == 0

    apply_result = run_cli("clean", "--apply", str(tmp_path))
    assert apply_result.returncode == 0
    run_path = Path(json.loads(apply_result.stdout)["quarantine_run_path"])
    assert run_path.exists()

    restore_result = run_cli("restore", str(run_path))
    assert restore_result.returncode == 0
    assert json.loads(restore_result.stdout)["restored"]
```

- [ ] **Step 2: Run CLI integration tests to verify they fail**

Run: `uv run pytest tests/test_cli_integration.py -v`

Expected: FAIL because `cli.py` still raises `command implementation is not wired yet`.

- [ ] **Step 3: Replace CLI with command wiring**

```python
# src/ai_slop_cleaner/cli.py
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ai_slop_cleaner.core import StaleManifestError, classify_path, ensure_current_manifest
from ai_slop_cleaner.models import CATEGORIES, MANIFEST_NAME
from ai_slop_cleaner.quarantine import apply_cleanup, plan_cleanup, restore_quarantine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-slop",
        description="AI Slop Cleaner: deterministic document classification and quarantine.",
    )
    subparsers = parser.add_subparsers(dest="command")

    classify = subparsers.add_parser("classify", help="Scan a folder and write ai-slop-manifest.json.")
    classify.add_argument("path", help="Folder to classify.")
    classify.add_argument("--max-bytes", type=int, default=1_000_000, help="Maximum bytes to read per file.")

    clean = subparsers.add_parser("clean", help="Plan or apply quarantine moves.")
    clean_mode = clean.add_mutually_exclusive_group(required=True)
    clean_mode.add_argument("--plan", action="store_true", help="Write a cleanup plan without moving files.")
    clean_mode.add_argument("--apply", action="store_true", help="Move eligible files into quarantine.")
    clean.add_argument("--rescan", action="store_true", help="Regenerate stale or missing manifest before cleaning.")
    clean.add_argument("path", help="Folder to clean.")

    restore = subparsers.add_parser("restore", help="Restore files from one quarantine run.")
    restore.add_argument("quarantine_run_path", help="Path to .ai-slop/quarantine/<timestamp>.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "classify":
            return _classify(args.path, max_bytes=args.max_bytes)
        if args.command == "clean":
            return _clean(args.path, plan=args.plan, apply=args.apply, rescan=args.rescan)
        if args.command == "restore":
            return _restore(args.quarantine_run_path)
    except StaleManifestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"{exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 2

    parser.error(f"unknown command: {args.command}")
    return 2


def _classify(path: str, *, max_bytes: int) -> int:
    manifest = classify_path(Path(path), max_bytes=max_bytes)
    target = Path(path).resolve()
    _print_json(
        {
            "manifest_path": str(target / MANIFEST_NAME),
            "counts": _counts(manifest),
        }
    )
    return 0


def _clean(path: str, *, plan: bool, apply: bool, rescan: bool) -> int:
    target = Path(path).resolve()
    manifest = ensure_current_manifest(target, rescan=rescan)
    if plan:
        cleanup_plan = plan_cleanup(target, manifest)
        _print_json(
            {
                "plan_path": str(target / ".ai-slop" / "cleanup-plan.json"),
                "move_count": len(cleanup_plan["moves"]),
                "moves": cleanup_plan["moves"],
            }
        )
        return 0
    if apply:
        run_path = apply_cleanup(target, manifest)
        _print_json({"quarantine_run_path": str(run_path)})
        return 0
    raise ValueError("clean requires --plan or --apply")


def _restore(path: str) -> int:
    summary = restore_quarantine(Path(path))
    _print_json(summary)
    return 0


def _counts(manifest: dict[str, Any]) -> dict[str, int]:
    return {category: len(manifest["categories"][category]) for category in CATEGORIES}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI integration tests**

Run: `uv run pytest tests/test_cli_integration.py -v`

Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_slop_cleaner/cli.py tests/test_cli_integration.py
git commit -m "feat: wire cli commands"
```

---

### Task 8: README Contract And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README with user-facing CLI contract**

````markdown
# AI Slop Cleaner

AI Slop Cleaner is a CLI-first context hygiene tool for coding agents.

It classifies project documents before an agent reads them, writes a traceable manifest, and can move safe cleanup candidates into quarantine. It never deletes files in v1.

## Install For Local Development

```bash
uv sync
```

## Commands

```bash
ai-slop classify <path>
ai-slop clean --plan <path>
ai-slop clean --apply <path>
ai-slop restore <quarantine-run-path>
```

## Agent Usage Timing

An agent should run:

```bash
ai-slop classify <project-path>
```

before building context from a project folder.

If any included file is added, removed, renamed, or modified after `ai-slop-manifest.json` was generated, the agent should rerun `classify`.

`clean --plan` and `clean --apply` refuse stale manifests unless `--rescan` is passed.

## Categories

Manifest categories:

```json
{
  "canonical": [],
  "duplicate": [],
  "stale": [],
  "conflict": [],
  "low_value": [],
  "needs_review": []
}
```

Agents should prefer `canonical`, avoid `duplicate`, `stale`, and `low_value`, and ask for human review before relying on `conflict` or `needs_review`.

## Cleanup

Preview cleanup:

```bash
ai-slop clean --plan <project-path>
```

Move safe candidates:

```bash
ai-slop clean --apply <project-path>
```

Eligible categories are `duplicate`, `stale`, and `low_value`.

Quarantined files move to:

```text
.ai-slop/quarantine/<timestamp>/<original-relative-path>
```

Restore one quarantine run:

```bash
ai-slop restore <project-path>/.ai-slop/quarantine/<timestamp>
```

Restore never overwrites an existing destination path.

## V1 Boundaries

Version 1 is deterministic and offline. It does not call external LLM APIs, does not call embedding providers, does not delete files, and does not include an IDE extension or MCP server implementation.
````

- [ ] **Step 2: Run full verification**

Run: `uv run pytest -v`

Expected: PASS.

- [ ] **Step 3: Run CLI smoke on a temporary fixture**

Run:

```bash
tmpdir="$(mktemp -d)"
printf '# Spec\nSame.\n' > "$tmpdir/a.md"
printf '# Spec\nSame.\n' > "$tmpdir/b.md"
uv run ai-slop classify "$tmpdir"
uv run ai-slop clean --plan "$tmpdir"
uv run ai-slop clean --apply "$tmpdir"
find "$tmpdir" -maxdepth 4 -type f | sort
```

Expected output includes:

```text
ai-slop-manifest.json
.ai-slop/cleanup-plan.json
.ai-slop/quarantine/
move-log.json
manifest.json
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document cli usage contract"
```

---

## Plan Self-Review

Spec coverage:

- CLI-first implementation is covered by Tasks 1 and 7.
- Scanner facts are covered by Task 2.
- Deterministic duplicate, stale, conflict, low-value, and needs-review categories are covered by Tasks 3 and 4.
- Manifest contract is covered by Task 3.
- Usage timing and stale manifest behavior are covered by Task 5 and Task 7.
- Quarantine move, plan, apply, and restore are covered by Task 6.
- README usage contract is covered by Task 8.
- MCP is intentionally out of implementation scope and represented by the reusable `core.py` API.

Placeholder scan:

- The plan has no placeholder markers or unspecified implementation steps.
- Each task has concrete tests, commands, expected outcomes, implementation content, and commit commands.

Type consistency:

- Scanner emits `DocumentRecord`.
- Classifier consumes `DocumentRecord` and emits `ClassificationResult`.
- Manifest writer consumes both and emits a manifest dict.
- Core API returns manifest dicts.
- Quarantine consumes manifest dicts.
- CLI only calls core and quarantine APIs.
