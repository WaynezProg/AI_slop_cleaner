from __future__ import annotations

import argparse


NOT_WIRED_MESSAGE = "command implementation is not wired yet"


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
    classify_parser.set_defaults(handler=_not_wired, command_parser=classify_parser)

    clean_parser = subparsers.add_parser(
        "clean",
        help="clean classified targets",
    )
    clean_mode = clean_parser.add_mutually_exclusive_group(required=True)
    clean_mode.add_argument("--plan", action="store_true", help="show planned changes")
    clean_mode.add_argument("--apply", action="store_true", help="apply planned changes")
    clean_parser.add_argument("path", help="path to clean")
    clean_parser.set_defaults(handler=_not_wired, command_parser=clean_parser)

    restore_parser = subparsers.add_parser(
        "restore",
        help="restore cleaned targets",
    )
    restore_parser.add_argument(
        "quarantine_run_path",
        help="quarantine run path to restore",
    )
    restore_parser.set_defaults(handler=_not_wired, command_parser=restore_parser)

    return parser


def _not_wired(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    parser.error(NOT_WIRED_MESSAGE)
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    return args.handler(args, args.command_parser)


if __name__ == "__main__":
    raise SystemExit(main())
