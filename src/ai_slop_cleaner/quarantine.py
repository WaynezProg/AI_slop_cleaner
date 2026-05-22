from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from ai_slop_cleaner.io_utils import write_json_file
from ai_slop_cleaner.models import MOVABLE_CATEGORIES


def plan_cleanup(
    target: str | Path,
    manifest: dict[str, Any],
    *,
    min_confidence: float = 0.75,
) -> dict[str, Any]:
    root = Path(target).resolve()
    created_at = _utc_now()
    moves = []

    for entry in manifest.get("files", []):
        if not isinstance(entry, dict):
            continue
        original_path = entry.get("path")
        category = entry.get("category")
        confidence = entry.get("confidence")
        if not isinstance(original_path, str):
            continue
        if category not in MOVABLE_CATEGORIES:
            continue
        if not isinstance(confidence, int | float) or confidence < min_confidence:
            continue
        if not _is_safe_relative_path(original_path):
            continue
        if not _is_safe_cleanup_source(root / original_path, root):
            continue

        moves.append(
            {
                "original_path": original_path,
                "category": category,
                "confidence": float(confidence),
                "reason": entry.get("reason", ""),
                "related_files": list(entry.get("related_files", [])),
            }
        )

    internal_path = root / ".ai-slop"
    _ensure_internal_directory(internal_path)
    plan = {
        "created_at": created_at,
        "target_path": str(root),
        "min_confidence": min_confidence,
        "moves": sorted(moves, key=lambda move: move["original_path"]),
    }
    _write_json(internal_path / "cleanup-plan.json", plan)
    return plan


def apply_cleanup(
    target: str | Path,
    manifest: dict[str, Any],
    *,
    min_confidence: float = 0.75,
) -> Path:
    root = Path(target).resolve()
    plan = plan_cleanup(root, manifest, min_confidence=min_confidence)
    quarantine_root = root / ".ai-slop" / "quarantine"
    _ensure_internal_directory(quarantine_root)
    run_path = _unique_run_path(quarantine_root)
    run_path.mkdir(parents=True)
    _write_json(run_path / "run.json", {"target_path": str(root), "created_at": _utc_now()})
    _write_json(run_path / "manifest.json", manifest)

    move_log = [
        {
            "original_path": move["original_path"],
            "quarantine_path": move["original_path"],
            "category": move["category"],
            "confidence": move["confidence"],
            "reason": move["reason"],
            "status": "planned",
        }
        for move in plan["moves"]
    ]
    _write_json(run_path / "move-log.json", move_log)

    for index, move in enumerate(plan["moves"]):
        original_path = move["original_path"]
        source = root / original_path
        destination = run_path / original_path
        if not _is_safe_cleanup_source(source, root):
            move_log[index]["status"] = "skipped"
            move_log[index]["skip_reason"] = "unsafe_source"
            _write_json(run_path / "move-log.json", move_log)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        move_log[index]["status"] = "moved"
        move_log[index]["moved_at"] = _utc_now()
        _write_json(run_path / "move-log.json", move_log)
    return run_path


def restore_quarantine(quarantine_run_path: str | Path) -> dict[str, Any]:
    run_path = Path(quarantine_run_path).resolve()
    move_log = _load_move_log(run_path)
    target_path = _restore_target_path(run_path)

    restored = []
    skipped = []
    for entry in move_log:
        if not isinstance(entry, dict):
            raise RuntimeError("Quarantine move log contains an invalid entry.")
        original_path = entry.get("original_path")
        if not isinstance(original_path, str):
            raise RuntimeError("Quarantine move log contains an invalid entry.")
        quarantine_path = entry.get("quarantine_path", original_path)
        if not isinstance(quarantine_path, str):
            raise RuntimeError("Quarantine move log contains an invalid entry.")
        if not _is_safe_relative_path(original_path) or not _is_safe_relative_path(quarantine_path):
            skipped.append({"path": original_path, "reason": "unsafe_path"})
            continue

        source = run_path / quarantine_path
        status = entry.get("status")
        source_exists = source.exists() or source.is_symlink()
        if status != "moved" and not source_exists:
            continue
        destination = target_path / original_path
        if destination.exists() or destination.is_symlink():
            skipped.append({"path": original_path, "reason": "destination_exists"})
            continue
        if not _is_safe_restore_destination(destination, target_path):
            skipped.append({"path": original_path, "reason": "unsafe_destination"})
            continue
        if not source_exists:
            skipped.append({"path": original_path, "reason": "quarantine_source_missing"})
            continue
        if not _is_safe_quarantine_source(source, run_path):
            skipped.append({"path": original_path, "reason": "unsafe_quarantine_source"})
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
        except OSError as error:
            skipped.append(
                {
                    "path": original_path,
                    "reason": "restore_failed",
                    "error": str(error),
                }
            )
            continue
        restored.append({"path": original_path})

    return {"restored": restored, "skipped": skipped}


def _unique_run_path(quarantine_root: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = quarantine_root / timestamp
    suffix = 1
    while candidate.exists():
        candidate = quarantine_root / f"{timestamp}-{suffix}"
        suffix += 1
    return candidate


def _ensure_internal_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_symlink():
            raise RuntimeError(f"Unsafe internal directory is a symlink: {path}")
        if not path.is_dir():
            raise RuntimeError(f"Unsafe internal path is not a directory: {path}")
        return

    parent = path.parent
    if parent.exists() or parent.is_symlink():
        if parent.is_symlink():
            raise RuntimeError(f"Unsafe internal directory parent is a symlink: {parent}")
        if not parent.is_dir():
            raise RuntimeError(f"Unsafe internal directory parent is not a directory: {parent}")
    path.mkdir()


def _load_move_log(run_path: Path) -> list[Any]:
    try:
        move_log = json.loads((run_path / "move-log.json").read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError("Quarantine move log is missing.") from error

    if not isinstance(move_log, list):
        raise RuntimeError("Quarantine move log must be a list.")
    return move_log


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _restore_target_path(run_path: Path) -> Path:
    try:
        run_metadata = json.loads((run_path / "run.json").read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError("Quarantine run metadata is missing target_path.") from error

    target_path = run_metadata.get("target_path")
    if not isinstance(target_path, str) or not target_path:
        raise RuntimeError("Quarantine run metadata is missing target_path.")
    return Path(target_path).resolve()


def _is_safe_restore_destination(destination: Path, target_path: Path) -> bool:
    root = target_path.resolve()
    try:
        destination.resolve(strict=False).relative_to(root)
        relative = destination.relative_to(root)
    except (OSError, ValueError):
        return False

    cursor = root
    for part in relative.parts[:-1]:
        cursor = cursor / part
        if cursor.is_symlink():
            return False
        if cursor.exists() and not cursor.is_dir():
            return False
    return True


def _is_safe_quarantine_source(source: Path, run_path: Path) -> bool:
    if source.is_symlink():
        return False
    if not source.is_file():
        return False
    try:
        source.resolve(strict=True).relative_to(run_path)
    except (OSError, ValueError):
        return False
    return True


def _is_safe_cleanup_source(source: Path, root: Path) -> bool:
    if source.is_symlink():
        return False
    if not source.is_file():
        return False
    try:
        source.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        return False
    return True


def _write_json(path: Path, data: Any) -> None:
    write_json_file(path, data)


def _is_safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and value not in {"", "."}
