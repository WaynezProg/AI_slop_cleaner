from __future__ import annotations

import json
import shutil

import pytest

from ai_slop_cleaner.core import classify_path
from ai_slop_cleaner.quarantine import apply_cleanup, plan_cleanup, restore_quarantine


def test_plan_cleanup_writes_plan_and_does_not_move_duplicate(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    plan = plan_cleanup(tmp_path, manifest)

    assert len(plan["moves"]) == 1
    assert plan["moves"][0]["category"] == "duplicate"
    assert plan["moves"][0]["original_path"] in {"a.md", "b.md"}
    assert (tmp_path / plan["moves"][0]["original_path"]).is_file()
    assert (tmp_path / ".ai-slop" / "cleanup-plan.json").is_file()


def test_plan_cleanup_ignores_repo_control_files(tmp_path) -> None:
    (tmp_path / ".gitignore").write_text(".venv\n", encoding="utf-8")
    (tmp_path / ".python-version").write_text("3.13\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("todo\n", encoding="utf-8")

    manifest = classify_path(tmp_path)
    plan = plan_cleanup(tmp_path, manifest)

    assert {entry["path"] for entry in manifest["files"]} == {"notes.md"}
    assert {move["original_path"] for move in plan["moves"]} == {"notes.md"}


def test_apply_cleanup_moves_only_eligible_categories(tmp_path) -> None:
    (tmp_path / "same.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "same-copy.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "summary.md").write_text("todo\n", encoding="utf-8")
    (tmp_path / "auth-a.md").write_text(
        "# Auth\nThe product must support SSO.\n",
        encoding="utf-8",
    )
    (tmp_path / "auth-b.md").write_text(
        "# Auth\nThe product must not support SSO.\n",
        encoding="utf-8",
    )
    manifest = classify_path(tmp_path)
    planned_paths = {entry["original_path"] for entry in plan_cleanup(tmp_path, manifest)["moves"]}

    run_path = apply_cleanup(tmp_path, manifest)

    assert run_path.is_dir()
    assert (run_path / "move-log.json").is_file()
    assert (run_path / "manifest.json").is_file()
    move_log = json.loads((run_path / "move-log.json").read_text(encoding="utf-8"))
    assert {entry["original_path"] for entry in move_log} == planned_paths == {
        "same-copy.md",
        "summary.md",
    }
    assert not (tmp_path / "same-copy.md").exists()
    assert not (tmp_path / "summary.md").exists()
    assert (run_path / "same-copy.md").is_file()
    assert (run_path / "summary.md").is_file()
    assert (tmp_path / "same.md").is_file()
    assert (tmp_path / "auth-a.md").is_file()
    assert (tmp_path / "auth-b.md").is_file()


def test_restore_quarantine_restores_without_overwriting_existing_destination(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    run_path = apply_cleanup(tmp_path, manifest)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")

    (tmp_path / moved_path).write_text("new content\n", encoding="utf-8")
    result = restore_quarantine(run_path)

    assert result["restored"] == []
    assert result["skipped"] == [{"path": moved_path, "reason": "destination_exists"}]
    assert (tmp_path / moved_path).read_text(encoding="utf-8") == "new content\n"
    assert (run_path / moved_path).is_file()


def test_restore_quarantine_restores_moved_files(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    run_path = apply_cleanup(tmp_path, manifest)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")

    result = restore_quarantine(run_path)

    assert result["skipped"] == []
    assert result["restored"] == [{"path": moved_path}]
    assert (tmp_path / moved_path).is_file()
    assert not (run_path / moved_path).exists()


def test_apply_cleanup_run_path_is_collision_safe(tmp_path, monkeypatch) -> None:
    import ai_slop_cleaner.quarantine as quarantine

    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    first_manifest = classify_path(tmp_path)

    class FrozenDateTime(quarantine.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 22, 12, 30, 0, tzinfo=tz)

    monkeypatch.setattr(quarantine, "datetime", FrozenDateTime)
    first_run = apply_cleanup(tmp_path, first_manifest)
    restore_quarantine(first_run)
    second_manifest = classify_path(tmp_path)

    second_run = apply_cleanup(tmp_path, second_manifest)

    assert first_run != second_run
    assert first_run.is_dir()
    assert second_run.is_dir()


def test_apply_cleanup_keeps_recoverable_move_log_when_later_move_fails(tmp_path, monkeypatch) -> None:
    import ai_slop_cleaner.quarantine as quarantine

    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "zz-low-value.md").write_text("todo\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    planned_paths = [entry["original_path"] for entry in plan_cleanup(tmp_path, manifest)["moves"]]
    assert len(planned_paths) == 2
    first_moved_path = planned_paths[0]
    real_move = shutil.move
    move_count = 0

    def fail_second_move(source, destination):
        nonlocal move_count
        move_count += 1
        if move_count == 2:
            raise RuntimeError("forced second move failure")
        return real_move(source, destination)

    monkeypatch.setattr(quarantine.shutil, "move", fail_second_move)

    with pytest.raises(RuntimeError, match="forced second move failure"):
        apply_cleanup(tmp_path, manifest)

    run_path = next((tmp_path / ".ai-slop" / "quarantine").iterdir())
    move_log_path = run_path / "move-log.json"
    assert move_log_path.is_file()
    move_log = json.loads(move_log_path.read_text(encoding="utf-8"))
    assert move_log[0]["original_path"] == first_moved_path
    assert move_log[0]["status"] == "moved"
    assert "moved_at" in move_log[0]
    assert move_log[1]["original_path"] == planned_paths[1]
    assert move_log[1]["status"] == "planned"

    monkeypatch.setattr(quarantine.shutil, "move", real_move)
    result = restore_quarantine(run_path)

    assert result["restored"] == [{"path": first_moved_path}]
    assert result["skipped"] == []
    assert (tmp_path / first_moved_path).is_file()
    assert (tmp_path / "zz-low-value.md").is_file()


def test_restore_recovers_file_when_move_log_write_fails_after_move(tmp_path, monkeypatch) -> None:
    import ai_slop_cleaner.quarantine as quarantine

    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")
    real_write_json = quarantine._write_json

    def fail_after_successful_move(path, data):
        if (
            path.name == "move-log.json"
            and isinstance(data, list)
            and any(entry.get("status") == "moved" for entry in data if isinstance(entry, dict))
        ):
            raise OSError("forced move-log write failure")
        real_write_json(path, data)

    monkeypatch.setattr(quarantine, "_write_json", fail_after_successful_move)

    with pytest.raises(OSError, match="forced move-log write failure"):
        apply_cleanup(tmp_path, manifest)

    run_path = next((tmp_path / ".ai-slop" / "quarantine").iterdir())
    assert not (tmp_path / moved_path).exists()
    assert (run_path / moved_path).is_file()

    monkeypatch.setattr(quarantine, "_write_json", real_write_json)
    result = restore_quarantine(run_path)

    assert result["restored"] == [{"path": moved_path}]
    assert result["skipped"] == []
    assert (tmp_path / moved_path).is_file()


def test_plan_cleanup_rejects_ai_slop_symlink(tmp_path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / ".ai-slop").symlink_to(external, target_is_directory=True)
    (tmp_path / "notes.md").write_text("todo\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    with pytest.raises(RuntimeError, match=".ai-slop"):
        plan_cleanup(tmp_path, manifest)

    assert not (external / "cleanup-plan.json").exists()


def test_apply_cleanup_rejects_quarantine_symlink(tmp_path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    internal = tmp_path / ".ai-slop"
    internal.mkdir()
    (internal / "quarantine").symlink_to(external, target_is_directory=True)
    (tmp_path / "notes.md").write_text("todo\n", encoding="utf-8")
    manifest = classify_path(tmp_path)

    with pytest.raises(RuntimeError, match="quarantine"):
        apply_cleanup(tmp_path, manifest)

    assert (tmp_path / "notes.md").is_file()
    assert list(external.iterdir()) == []


def test_restore_quarantine_uses_apply_target_not_manifest_target_path(tmp_path) -> None:
    target = tmp_path / "target"
    other = tmp_path / "other"
    target.mkdir()
    other.mkdir()
    (target / "a.md").write_text("# Same\n", encoding="utf-8")
    (target / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(target)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")
    manifest["target_path"] = str(other)

    run_path = apply_cleanup(target, manifest)
    result = restore_quarantine(run_path)

    assert result["restored"] == [{"path": moved_path}]
    assert result["skipped"] == []
    assert (target / moved_path).is_file()
    assert not (other / moved_path).exists()


def test_restore_quarantine_requires_run_metadata_and_does_not_fallback_to_manifest_target(tmp_path) -> None:
    target = tmp_path / "target"
    other = tmp_path / "other"
    target.mkdir()
    other.mkdir()
    (target / "a.md").write_text("# Same\n", encoding="utf-8")
    (target / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(target)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")
    manifest["target_path"] = str(other)
    run_path = apply_cleanup(target, manifest)
    (run_path / "run.json").unlink()

    with pytest.raises(RuntimeError, match="run metadata"):
        restore_quarantine(run_path)

    assert not (target / moved_path).exists()
    assert not (other / moved_path).exists()
    assert (run_path / moved_path).is_file()


def test_restore_quarantine_treats_broken_symlink_destination_as_existing(tmp_path) -> None:
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    run_path = apply_cleanup(tmp_path, manifest)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")
    destination = tmp_path / moved_path
    destination.symlink_to(tmp_path / "missing-target")

    result = restore_quarantine(run_path)

    assert result["restored"] == []
    assert result["skipped"] == [{"path": moved_path, "reason": "destination_exists"}]
    assert destination.is_symlink()
    assert not destination.exists()
    assert (run_path / moved_path).is_file()


def test_restore_quarantine_skips_destination_with_symlink_parent(tmp_path) -> None:
    target = tmp_path / "target"
    external = tmp_path / "external"
    target.mkdir()
    external.mkdir()
    (target / "docs").mkdir()
    (target / "docs" / "scratch.md").write_text("todo\n", encoding="utf-8")
    manifest = classify_path(target)
    run_path = apply_cleanup(target, manifest)

    shutil.rmtree(target / "docs")
    (target / "docs").symlink_to(external, target_is_directory=True)
    result = restore_quarantine(run_path)

    assert result["restored"] == []
    assert result["skipped"] == [{"path": "docs/scratch.md", "reason": "unsafe_destination"}]
    assert not (external / "scratch.md").exists()
    assert (run_path / "docs" / "scratch.md").is_file()


def test_restore_quarantine_skips_symlink_quarantine_source(tmp_path) -> None:
    external = tmp_path / "external.md"
    external.write_text("# External\n", encoding="utf-8")
    (tmp_path / "a.md").write_text("# Same\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\n", encoding="utf-8")
    manifest = classify_path(tmp_path)
    run_path = apply_cleanup(tmp_path, manifest)
    moved_path = next(entry["path"] for entry in manifest["files"] if entry["category"] == "duplicate")
    source = run_path / moved_path
    source.unlink()
    source.symlink_to(external)

    result = restore_quarantine(run_path)

    assert result["restored"] == []
    assert result["skipped"] == [{"path": moved_path, "reason": "unsafe_quarantine_source"}]
    assert (tmp_path / moved_path).exists() is False
    assert source.is_symlink()
