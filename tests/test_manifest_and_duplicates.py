from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ai_slop_cleaner.classifier import classify_records
from ai_slop_cleaner.manifest_writer import build_manifest
from ai_slop_cleaner.models import DocumentRecord
from ai_slop_cleaner.scanner import scan_documents


def test_same_content_different_names_becomes_duplicate(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")

    results = classify_records(scan_documents(tmp_path))

    categories = sorted(result.category for result in results)
    assert categories == ["canonical", "duplicate"]
    duplicate = next(result for result in results if result.category == "duplicate")
    assert duplicate.confidence == 0.99
    assert duplicate.signals[0]["name"] == "exact_hash_duplicate"
    canonical = next(result for result in results if result.category == "canonical")
    assert canonical.related_files == [duplicate.path]
    assert duplicate.related_files == [canonical.path]


def test_copy_filename_loses_to_original_even_when_newer(tmp_path) -> None:
    spec_path = tmp_path / "spec.md"
    copy_path = tmp_path / "spec-copy.md"
    spec_path.write_text("# Spec\n", encoding="utf-8")
    copy_path.write_text("# Spec\n", encoding="utf-8")
    copy_path.touch()

    results = classify_records(scan_documents(tmp_path))

    results_by_path = {result.path: result for result in results}
    assert results_by_path["spec.md"].category == "canonical"
    assert results_by_path["spec-copy.md"].category == "duplicate"
    assert results_by_path["spec.md"].related_files == ["spec-copy.md"]
    assert results_by_path["spec-copy.md"].related_files == ["spec.md"]


def test_canonical_true_outranks_status_final(tmp_path) -> None:
    canonical_path = tmp_path / "canonical.md"
    final_path = tmp_path / "final.md"
    canonical_path.write_text(
        """---
canonical: true
---
# Spec
""",
        encoding="utf-8",
    )
    final_path.write_text(
        """---
status: final
---
# Spec
""",
        encoding="utf-8",
    )

    scanned = scan_documents(tmp_path)
    shared_hash = scanned[0].hash
    records = [replace(record, hash=shared_hash) for record in scanned]
    results = classify_records(records)

    results_by_path = {result.path: result for result in results}
    assert results_by_path["canonical.md"].category == "canonical"
    assert results_by_path["final.md"].category == "duplicate"


def test_manifest_has_category_buckets_and_file_entries(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    records = scan_documents(tmp_path)
    results = classify_records(records)

    manifest = build_manifest(tmp_path, records, results, {"max_bytes": 1_000_000})

    assert manifest["schema_version"] == 1
    assert manifest["target_path"] == str(Path(tmp_path).resolve())
    assert sorted(manifest["categories"]) == [
        "canonical",
        "conflict",
        "duplicate",
        "low_value",
        "needs_review",
        "stale",
    ]
    assert len(manifest["files"]) == 2
    assert len(manifest["categories"]["canonical"]) == 1
    assert len(manifest["categories"]["duplicate"]) == 1
    for entry in manifest["files"]:
        assert entry["reason"]
        assert entry["signals"]


def test_manifest_preserves_scanner_error_evidence(tmp_path) -> None:
    record = DocumentRecord(
        relative_path="bad.bin",
        absolute_path=str(tmp_path / "bad.bin"),
        hash="abc123",
        size=7,
        mtime=1.0,
        extension=".bin",
        title=None,
        frontmatter={},
        normalized_text="",
        headings=[],
        references=[],
        errors=["binary_file"],
    )

    results = classify_records([record])
    manifest = build_manifest(tmp_path, [record], results, {"max_bytes": 1_000_000})

    assert manifest["categories"]["needs_review"] == ["bad.bin"]
    entry = manifest["files"][0]
    assert entry["category"] == "needs_review"
    assert entry["errors"] == ["binary_file"]
    assert entry["signals"][0]["name"] == "scanner_error"
    assert entry["reason"]
