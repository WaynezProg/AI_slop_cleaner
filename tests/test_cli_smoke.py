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


def test_console_script_help_runs() -> None:
    result = subprocess.run(
        ["uv", "run", "ai-slop", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "AI Slop Cleaner" in result.stdout
    assert "classify" in result.stdout
    assert "clean" in result.stdout
    assert "restore" in result.stdout


def test_console_script_requires_subcommand() -> None:
    result = subprocess.run(
        ["uv", "run", "ai-slop"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "usage: ai-slop" in result.stderr


def test_clean_plan_missing_manifest_uses_subcommand_usage() -> None:
    result = subprocess.run(
        ["uv", "run", "ai-slop", "clean", "--plan", "."],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Manifest not found" in result.stderr
    assert "Run ai-slop classify" in result.stderr
    assert "pass --rescan to clean" in result.stderr
    assert "command implementation is not wired yet" not in result.stderr
    assert "usage: ai-slop clean" in result.stderr
