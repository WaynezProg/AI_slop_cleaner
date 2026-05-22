from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from ai_slop_cleaner.classifier import classify_records
from ai_slop_cleaner.manifest_writer import build_manifest, write_manifest
from ai_slop_cleaner.models import MANIFEST_NAME
from ai_slop_cleaner.scanner import scan_documents


class StaleManifestError(RuntimeError):
    """Raised when a manifest is missing or no longer matches the target tree."""


def classify_path(
    target: str | Path,
    *,
    write: bool = True,
    max_bytes: int = 1_000_000,
) -> dict[str, Any]:
    records = scan_documents(target, max_bytes=max_bytes)
    results = classify_records(records)
    manifest = build_manifest(
        target,
        records,
        results,
        {"max_bytes": max_bytes},
    )
    if write:
        write_manifest(target, manifest)
    return manifest


def load_manifest(target: str | Path) -> dict[str, Any]:
    path = Path(target).resolve() / MANIFEST_NAME
    if path.is_symlink():
        raise RuntimeError(f"Refusing to read manifest through symlink: {path}")
    if path.exists() and not path.is_file():
        raise RuntimeError(f"Manifest path is not a regular file: {path}")
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def manifest_is_current(target: str | Path, manifest: dict[str, Any]) -> bool:
    root = Path(target).resolve()
    if manifest.get("schema_version") != 1:
        return False
    if manifest.get("target_path") != str(root):
        return False

    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        return False

    manifest_snapshot: dict[str, tuple[str | None, int, float]] = {}
    for entry in manifest_files:
        if not isinstance(entry, dict):
            return False
        path = entry.get("path")
        size = entry.get("size")
        file_hash = entry.get("hash")
        mtime = entry.get("mtime")
        if not isinstance(path, str) or not isinstance(size, int):
            return False
        if file_hash is not None and not isinstance(file_hash, str):
            return False
        if not isinstance(mtime, int | float):
            return False
        manifest_snapshot[path] = (file_hash, size, float(mtime))

    max_bytes = manifest_max_bytes(manifest)
    records = scan_documents(target, max_bytes=max_bytes)
    current_snapshot = {
        record.relative_path: (
            record.hash,
            record.size,
            record.mtime,
        )
        for record in records
    }
    if current_snapshot != manifest_snapshot:
        return False

    current_manifest = build_manifest(
        root,
        records,
        classify_records(records),
        {"max_bytes": max_bytes},
    )
    return _classification_snapshot(manifest) == _classification_snapshot(current_manifest)


def ensure_current_manifest(
    target: str | Path,
    *,
    rescan: bool = False,
) -> dict[str, Any]:
    root = Path(target).resolve()
    try:
        manifest = load_manifest(root)
    except FileNotFoundError as error:
        if rescan:
            return classify_path(root)
        raise StaleManifestError(
            f"Manifest not found: {root / MANIFEST_NAME}. "
            f"Run ai-slop classify {root} or pass --rescan to clean."
        ) from error

    if manifest_is_current(root, manifest):
        return manifest

    if rescan:
        return classify_path(root, max_bytes=manifest_max_bytes(manifest))
    raise StaleManifestError(
        f"Manifest is stale. Run ai-slop classify {root} or pass --rescan to clean."
    )


def manifest_max_bytes(manifest: dict[str, Any]) -> int:
    scanner_config = manifest.get("scanner_config", {})
    if not isinstance(scanner_config, dict):
        return 1_000_000

    max_bytes = scanner_config.get("max_bytes", 1_000_000)
    if isinstance(max_bytes, int) and max_bytes > 0:
        return max_bytes
    return 1_000_000


def _classification_snapshot(manifest: dict[str, Any]) -> dict[str, Any]:
    files = manifest.get("files")
    if not isinstance(files, list):
        return {}

    return {
        "categories": manifest.get("categories"),
        "files": [
            {
                key: entry.get(key)
                for key in (
                    "path",
                    "category",
                    "confidence",
                    "signals",
                    "reason",
                    "related_files",
                    "errors",
                )
            }
            for entry in files
            if isinstance(entry, dict)
        ],
    }
