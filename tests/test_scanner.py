from __future__ import annotations

from ai_slop_cleaner.scanner import scan_documents


def test_scan_documents_extracts_markdown_facts(tmp_path) -> None:
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(
        """---
title: Payment Spec
status: canonical
---
# Payment Spec

See [API](api.md) and [[notes]].
""",
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
    assert record.references == ["api.md", "notes"]
    assert record.errors == []


def test_scan_documents_ignores_headings_and_references_in_fenced_code(tmp_path) -> None:
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(
        """# Real

See [Good](good.md).

```markdown
# Fake
See [Bad](fake.md).
```
""",
        encoding="utf-8",
    )

    records = scan_documents(tmp_path)

    assert len(records) == 1
    assert records[0].title == "Real"
    assert records[0].headings == ["Real"]
    assert records[0].references == ["good.md"]


def test_scan_documents_body_text_preserves_punctuation_outside_fenced_code(tmp_path) -> None:
    spec_path = tmp_path / "spec.md"
    spec_path.write_text(
        """---
title: Auth Spec
---
The product must support SSO. Customers use it daily.

```markdown
The product must not support SSO.
```
""",
        encoding="utf-8",
    )

    records = scan_documents(tmp_path)

    assert len(records) == 1
    assert "The product must support SSO. Customers use it daily." in records[0].body_text
    assert "must not support SSO" not in records[0].body_text


def test_scan_documents_skips_ai_slop_internal_folder(tmp_path) -> None:
    (tmp_path / "keep.md").write_text("# Keep\n", encoding="utf-8")
    internal_dir = tmp_path / ".ai-slop"
    internal_dir.mkdir()
    (internal_dir / "internal.md").write_text("# Internal\n", encoding="utf-8")

    records = scan_documents(tmp_path)

    assert [record.relative_path for record in records] == ["keep.md"]


def test_scan_documents_skips_dependency_and_build_artifact_folders(tmp_path) -> None:
    ignored_dirs = [".venv", "dist", "build", "node_modules"]
    for dirname in ignored_dirs:
        folder = tmp_path / dirname
        folder.mkdir()
        (folder / "artifact.md").write_text("# Artifact\n", encoding="utf-8")
    (tmp_path / "live.md").write_text("# Live\n", encoding="utf-8")

    records = scan_documents(tmp_path)

    assert [record.relative_path for record in records] == ["live.md"]


def test_scan_documents_marks_binary_file(tmp_path) -> None:
    binary_path = tmp_path / "blob.bin"
    binary_path.write_bytes(b"abc\x00def")

    records = scan_documents(tmp_path)

    assert len(records) == 1
    assert records[0].errors == ["binary_file"]
    assert records[0].normalized_text == ""


def test_scan_documents_marks_oversized_file(tmp_path) -> None:
    text_path = tmp_path / "large.md"
    text_path.write_text("0123456789abcdefg", encoding="utf-8")

    records = scan_documents(tmp_path, max_bytes=16)

    assert len(records) == 1
    assert records[0].errors == ["oversized_file"]
    assert records[0].normalized_text == ""


def test_scan_documents_does_not_hash_oversized_file(tmp_path, monkeypatch) -> None:
    text_path = tmp_path / "large.md"
    text_path.write_text("0123456789abcdefg", encoding="utf-8")

    def fail_hash(_path):
        raise AssertionError("oversized file should not be hashed")

    monkeypatch.setattr("ai_slop_cleaner.scanner._hash_file", fail_hash)

    records = scan_documents(tmp_path, max_bytes=16)

    assert len(records) == 1
    assert records[0].hash is None
    assert records[0].errors == ["oversized_file"]
