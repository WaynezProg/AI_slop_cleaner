from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ai_slop_cleaner.core import (
    StaleManifestError,
    classify_path,
    ensure_current_manifest,
    manifest_max_bytes,
)
from ai_slop_cleaner.models import CATEGORIES, MANIFEST_NAME
from ai_slop_cleaner.quarantine import apply_cleanup, plan_cleanup, restore_quarantine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-slop",
        description="AI Slop Cleaner",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    classify_parser = subparsers.add_parser(
        "classify",
        help="classify cleanup targets",
    )
    classify_parser.add_argument("path", help="path to classify")
    classify_parser.add_argument(
        "--max-bytes",
        type=int,
        default=1_000_000,
        help="maximum bytes to scan per file",
    )
    classify_parser.set_defaults(handler=_handle_classify, command_parser=classify_parser)

    clean_parser = subparsers.add_parser(
        "clean",
        help="clean classified targets",
    )
    clean_mode = clean_parser.add_mutually_exclusive_group(required=True)
    clean_mode.add_argument("--plan", action="store_true", help="show planned changes")
    clean_mode.add_argument("--apply", action="store_true", help="apply planned changes")
    clean_parser.add_argument(
        "--rescan",
        action="store_true",
        help="regenerate a missing or stale manifest before cleaning",
    )
    clean_parser.add_argument("path", help="path to clean")
    clean_parser.set_defaults(handler=_handle_clean, command_parser=clean_parser)

    restore_parser = subparsers.add_parser(
        "restore",
        help="restore cleaned targets",
    )
    restore_parser.add_argument(
        "quarantine_run_path",
        help="quarantine run path to restore",
    )
    restore_parser.set_defaults(handler=_handle_restore, command_parser=restore_parser)

    return parser


def _handle_classify(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    manifest = classify_path(args.path, max_bytes=args.max_bytes)
    _print_json(
        {
            "manifest_path": str(Path(args.path).resolve() / MANIFEST_NAME),
            "counts": _category_counts(manifest),
        }
    )
    return 0


def _handle_clean(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    manifest = ensure_current_manifest(args.path, rescan=args.rescan)
    if args.plan:
        plan = plan_cleanup(args.path, manifest)
        _print_json(
            {
                "plan_path": str(Path(args.path).resolve() / ".ai-slop" / "cleanup-plan.json"),
                "move_count": len(plan["moves"]),
                "moves": plan["moves"],
            }
        )
        return 0

    run_path = apply_cleanup(args.path, manifest)
    classify_path(args.path, max_bytes=manifest_max_bytes(manifest))
    _print_json(
        {
            "quarantine_run_path": str(run_path),
            "manifest_path": str(Path(args.path).resolve() / MANIFEST_NAME),
        }
    )
    return 0


def _handle_restore(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    _print_json(restore_quarantine(args.quarantine_run_path))
    return 0


def _category_counts(manifest: dict[str, Any]) -> dict[str, int]:
    categories = manifest.get("categories", {})
    return {
        category: len(categories.get(category, [])) if isinstance(categories, dict) else 0
        for category in CATEGORIES
    }


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, sort_keys=True))


def _print_cli_error(parser: argparse.ArgumentParser, error: Exception) -> None:
    parser.print_usage(sys.stderr)
    print(f"{parser.prog}: error: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args, args.command_parser)
    except (StaleManifestError, OSError, RuntimeError, json.JSONDecodeError) as error:
        _print_cli_error(args.command_parser, error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
