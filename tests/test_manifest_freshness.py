from __future__ import annotations

import os

import pytest

from ai_slop_cleaner.core import (
    StaleManifestError,
    classify_path,
    ensure_current_manifest,
    manifest_is_current,
)
from ai_slop_cleaner.models import MANIFEST_NAME


def test_classify_path_writes_manifest_and_returns_canonical_categories(tmp_path) -> None:
    (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")

    manifest = classify_path(tmp_path)

    assert (tmp_path / MANIFEST_NAME).is_file()
    assert manifest["categories"]["canonical"] == ["spec.md"]
    assert manifest["scanner_config"] == {"max_bytes": 1_000_000}


def test_manifest_is_current_ignores_future_mtime_when_snapshot_matches(tmp_path) -> None:
    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    newer_mtime = manifest["generated_at_epoch"] + 5
    os.utime(doc_path, (newer_mtime, newer_mtime))

    assert manifest_is_current(tmp_path, manifest) is True


def test_manifest_is_current_returns_false_when_manifest_file_was_deleted(tmp_path) -> None:
    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    doc_path.unlink()

    assert manifest_is_current(tmp_path, manifest) is False


def test_manifest_is_current_returns_false_when_path_set_changes(tmp_path) -> None:
    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    doc_path.rename(tmp_path / "renamed-spec.md")
    (tmp_path / "new.md").write_text("# New\n", encoding="utf-8")

    assert manifest_is_current(tmp_path, manifest) is False


def test_manifest_is_current_returns_false_when_content_changes_with_same_mtime(tmp_path) -> None:
    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    original_mtime = manifest["files"][0]["mtime"]

    doc_path.write_text("# Spac\n", encoding="utf-8")
    os.utime(doc_path, (original_mtime, original_mtime))

    assert manifest_is_current(tmp_path, manifest) is False


def test_manifest_is_current_returns_false_when_oversized_content_changes_same_size(tmp_path) -> None:
    doc_path = tmp_path / "large.md"
    doc_path.write_text("abcde", encoding="utf-8")
    manifest = classify_path(tmp_path, max_bytes=4)

    doc_path.write_text("vwxyz", encoding="utf-8")
    newer_mtime = manifest["generated_at_epoch"] + 5
    os.utime(doc_path, (newer_mtime, newer_mtime))

    assert manifest["files"][0]["hash"] is None
    assert manifest_is_current(tmp_path, manifest) is False


def test_ensure_current_manifest_raises_when_manifest_missing_and_rescan_false(tmp_path) -> None:
    with pytest.raises(StaleManifestError, match="missing"):
        ensure_current_manifest(tmp_path)


def test_ensure_current_manifest_raises_when_manifest_stale_and_rescan_false(tmp_path) -> None:
    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n", encoding="utf-8")
    classify_path(tmp_path)
    doc_path.write_text("# Updated Spec\n", encoding="utf-8")

    with pytest.raises(StaleManifestError, match="stale"):
        ensure_current_manifest(tmp_path)


def test_ensure_current_manifest_regenerates_missing_manifest_when_rescan_true(tmp_path) -> None:
    (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")

    manifest = ensure_current_manifest(tmp_path, rescan=True)

    assert (tmp_path / MANIFEST_NAME).is_file()
    assert manifest["categories"]["canonical"] == ["spec.md"]


def test_ensure_current_manifest_regenerates_stale_manifest_when_rescan_true(tmp_path) -> None:
    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n", encoding="utf-8")
    stale_manifest = classify_path(tmp_path)
    newer_mtime = stale_manifest["generated_at_epoch"] + 5
    os.utime(doc_path, (newer_mtime, newer_mtime))
    doc_path.write_text("# Updated Spec\n", encoding="utf-8")

    manifest = ensure_current_manifest(tmp_path, rescan=True)

    assert manifest["generated_at_epoch"] > stale_manifest["generated_at_epoch"]
    assert manifest["categories"]["canonical"] == ["spec.md"]
    assert manifest_is_current(tmp_path, manifest) is True


def test_ensure_current_manifest_preserves_existing_scanner_config_on_rescan(tmp_path) -> None:
    large_path = tmp_path / "large.md"
    large_path.write_text("12345", encoding="utf-8")
    stale_manifest = classify_path(tmp_path, max_bytes=4)
    (tmp_path / "new.md").write_text("# New\n", encoding="utf-8")

    manifest = ensure_current_manifest(tmp_path, rescan=True)

    assert stale_manifest["scanner_config"] == {"max_bytes": 4}
    assert manifest["scanner_config"] == {"max_bytes": 4}
    large_entry = next(entry for entry in manifest["files"] if entry["path"] == "large.md")
    assert large_entry["errors"] == ["oversized_file"]
    assert manifest_is_current(tmp_path, manifest) is True
