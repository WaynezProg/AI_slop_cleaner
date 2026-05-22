from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    return json.loads(path.read_text(encoding="utf-8"))


def manifest_is_current(target: str | Path, manifest: dict[str, Any]) -> bool:
    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, list):
        return False

    manifest_snapshot: dict[str, tuple[str | None, int, float | None]] = {}
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
        if file_hash is None and not isinstance(mtime, int | float):
            return False
        manifest_snapshot[path] = (file_hash, size, float(mtime) if file_hash is None else None)

    max_bytes = _manifest_max_bytes(manifest)
    current_snapshot = {
        record.relative_path: (
            record.hash,
            record.size,
            record.mtime if record.hash is None else None,
        )
        for record in scan_documents(target, max_bytes=max_bytes)
    }
    return current_snapshot == manifest_snapshot


def ensure_current_manifest(
    target: str | Path,
    *,
    rescan: bool = False,
) -> dict[str, Any]:
    try:
        manifest = load_manifest(target)
    except FileNotFoundError as error:
        if rescan:
            return classify_path(target)
        raise StaleManifestError("Manifest is missing; run classify with rescan enabled.") from error

    if manifest_is_current(target, manifest):
        return manifest

    if rescan:
        return classify_path(target, max_bytes=_manifest_max_bytes(manifest))
    raise StaleManifestError("Manifest is stale; run classify with rescan enabled.")


def _manifest_max_bytes(manifest: dict[str, Any]) -> int:
    scanner_config = manifest.get("scanner_config", {})
    if not isinstance(scanner_config, dict):
        return 1_000_000

    max_bytes = scanner_config.get("max_bytes", 1_000_000)
    if isinstance(max_bytes, int) and max_bytes > 0:
        return max_bytes
    return 1_000_000
