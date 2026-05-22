from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ai_slop_cleaner.models import CATEGORIES, MANIFEST_NAME


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ai_slop_cleaner.cli", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def seed_cleanup_target(path: Path) -> None:
    (path / "same.md").write_text("# Same\n", encoding="utf-8")
    (path / "same-copy.md").write_text("# Same\n", encoding="utf-8")
    (path / "summary.md").write_text("todo\n", encoding="utf-8")


def test_classify_writes_manifest_and_prints_counts_for_all_categories(tmp_path) -> None:
    seed_cleanup_target(tmp_path)

    result = run_cli("classify", str(tmp_path))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["manifest_path"] == str(tmp_path / MANIFEST_NAME)
    assert output["counts"].keys() == set(CATEGORIES)
    assert output["counts"]["canonical"] == 1
    assert output["counts"]["duplicate"] == 1
    assert output["counts"]["low_value"] == 1
    assert (tmp_path / MANIFEST_NAME).is_file()
    assert result.stderr == ""


def test_clean_plan_refuses_stale_manifest_without_rescan(tmp_path) -> None:
    seed_cleanup_target(tmp_path)
    assert run_cli("classify", str(tmp_path)).returncode == 0
    (tmp_path / "new.md").write_text("# New\n", encoding="utf-8")

    result = run_cli("clean", "--plan", str(tmp_path))

    assert result.returncode == 2
    assert "Manifest is stale" in result.stderr
    assert "Run ai-slop classify" in result.stderr
    assert "pass --rescan to clean" in result.stderr
    assert "classify with rescan enabled" not in result.stderr
    assert result.stdout == ""


def test_clean_plan_refuses_missing_manifest_without_placeholder(tmp_path) -> None:
    seed_cleanup_target(tmp_path)

    result = run_cli("clean", "--plan", str(tmp_path))

    assert result.returncode == 2
    assert "Manifest not found" in result.stderr
    assert "Run ai-slop classify" in result.stderr
    assert "pass --rescan to clean" in result.stderr
    assert "classify with rescan enabled" not in result.stderr
    assert "command implementation is not wired yet" not in result.stderr
    assert result.stdout == ""


def test_clean_plan_rescans_stale_manifest_when_requested(tmp_path) -> None:
    seed_cleanup_target(tmp_path)
    assert run_cli("classify", str(tmp_path)).returncode == 0
    new_file = tmp_path / "new.md"
    new_file.write_text("# New\n", encoding="utf-8")
    os.utime(new_file, None)

    result = run_cli("clean", "--plan", "--rescan", str(tmp_path))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["plan_path"] == str(tmp_path / ".ai-slop" / "cleanup-plan.json")
    assert output["move_count"] == 2
    assert {move["original_path"] for move in output["moves"]} == {"same-copy.md", "summary.md"}
    assert result.stderr == ""


def test_clean_plan_with_current_manifest_prints_plan_json(tmp_path) -> None:
    seed_cleanup_target(tmp_path)
    assert run_cli("classify", str(tmp_path)).returncode == 0

    result = run_cli("clean", "--plan", str(tmp_path))

    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["plan_path"] == str(tmp_path / ".ai-slop" / "cleanup-plan.json")
    assert output["move_count"] == 2
    assert {move["original_path"] for move in output["moves"]} == {"same-copy.md", "summary.md"}
    assert result.stderr == ""


def test_clean_apply_and_restore_print_machine_readable_json(tmp_path) -> None:
    seed_cleanup_target(tmp_path)
    assert run_cli("classify", str(tmp_path)).returncode == 0

    apply_result = run_cli("clean", "--apply", str(tmp_path))

    assert apply_result.returncode == 0
    apply_output = json.loads(apply_result.stdout)
    quarantine_run_path = Path(apply_output["quarantine_run_path"])
    assert quarantine_run_path.is_dir()
    assert not (tmp_path / "same-copy.md").exists()
    assert not (tmp_path / "summary.md").exists()

    restore_result = run_cli("restore", str(quarantine_run_path))

    assert restore_result.returncode == 0
    restore_output = json.loads(restore_result.stdout)
    assert {entry["path"] for entry in restore_output["restored"]} == {
        "same-copy.md",
        "summary.md",
    }
    assert restore_output["skipped"] == []
    assert (tmp_path / "same-copy.md").is_file()
    assert (tmp_path / "summary.md").is_file()
