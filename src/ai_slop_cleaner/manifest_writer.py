from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_slop_cleaner.io_utils import write_json_file
from ai_slop_cleaner.models import (
    CATEGORIES,
    MANIFEST_NAME,
    ClassificationResult,
    DocumentRecord,
)


def build_manifest(
    target: str | Path,
    records: list[DocumentRecord],
    results: list[ClassificationResult],
    scanner_config: dict[str, Any],
) -> dict[str, Any]:
    root = Path(target).resolve()
    generated_at_epoch = time.time()
    records_by_path = {record.relative_path: record for record in records}
    sorted_results = sorted(results, key=lambda result: result.path)
    categories: dict[str, list[str]] = {category: [] for category in CATEGORIES}
    files: list[dict[str, Any]] = []

    for result in sorted_results:
        record = records_by_path[result.path]
        entry = result.to_manifest_entry(record)
        files.append(entry)
        categories[result.category].append(result.path)

    return {
        "schema_version": 1,
        "target_path": str(root),
        "generated_at": datetime.fromtimestamp(generated_at_epoch, tz=timezone.utc).isoformat(),
        "generated_at_epoch": generated_at_epoch,
        "scanner_config": dict(scanner_config),
        "categories": categories,
        "files": files,
    }


def write_manifest(target: str | Path, manifest: dict[str, Any]) -> Path:
    path = Path(target).resolve() / MANIFEST_NAME
    write_json_file(path, manifest)
    return path
