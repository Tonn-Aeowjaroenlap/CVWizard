"""Command line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .validation import validate_path


def main() -> int:
    parser = argparse.ArgumentParser(prog="cvwizard")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a v1 YAML dataset")
    validate.add_argument("path", type=Path, help="YAML file or directory containing dataset.yaml")
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate_path(args.path)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"Valid CVWizard dataset: {args.path}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
