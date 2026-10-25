"""Command line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .ingestion import ingest
from .output_policy import private_output_path
from .review import export_facts, load_intake
from .validation import validate_path


def main() -> int:
    parser = argparse.ArgumentParser(prog="cvwizard")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate a v1 YAML dataset")
    validate.add_argument("path", type=Path, help="YAML file or directory containing dataset.yaml")
    intake_command = commands.add_parser("ingest", help="extract unverified assertions from local files")
    intake_command.add_argument("sources", nargs="+", type=Path)
    intake_command.add_argument("--output", required=True, type=Path)
    intake_command.add_argument("--private-output-root", type=Path, help="explicit absolute private root outside Git")
    intake_command.add_argument("--supersedes", action="append", default=[], metavar="FILENAME=SOURCE_ID")
    check = commands.add_parser("validate-intake", help="validate an intake and its review ledger")
    check.add_argument("path", type=Path)
    report = commands.add_parser("review-report", help="show IDs and review state without source text")
    report.add_argument("path", type=Path)
    export = commands.add_parser("export-facts", help="write conservatively permitted reviewed facts")
    export.add_argument("path", type=Path)
    export.add_argument("--audience", choices=["personal_cv", "external", "public"], required=True)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--private-output-root", type=Path, help="explicit absolute private root outside Git")
    args = parser.parse_args()
    if args.command == "validate":
        errors = validate_path(args.path)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"Valid CVWizard dataset: {args.path}")
        return 0
    if args.command == "ingest":
        try:
            output = private_output_path(args.output, args.private_output_root)
            supersedes = dict(pair.split("=", 1) for pair in args.supersedes)
            if any(not key or not value for key, value in supersedes.items()):
                raise ValueError("--supersedes expects FILENAME=SOURCE_ID")
            if output.exists():
                raise ValueError("output already exists; ingestion never overwrites review history")
            intake = ingest(args.sources, supersedes=supersedes)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(yaml.safe_dump(intake.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print(f"Created unreviewed intake: {args.output} ({len(intake.sources)} sources, {len(intake.assertions)} assertions, {len(intake.conflicts)} conflict groups)")
        return 0
    intake, errors = load_intake(args.path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    assert intake is not None
    if args.command == "validate-intake":
        print(f"Valid CVWizard intake: {args.path}")
        return 0
    if args.command == "review-report":
        latest = {decision.assertion_id: decision for decision in intake.decisions}
        for assertion in intake.assertions:
            decision = latest.get(assertion.assertion_id)
            print(f"{assertion.assertion_id} {assertion.source_id} {assertion.location} {decision.decision if decision else 'PENDING'}")
        for conflict in intake.conflicts:
            print(f"CONFLICT {conflict.field}: {', '.join(conflict.assertion_ids)}")
        return 0
    if args.command == "export-facts":
        try:
            output = private_output_path(args.output, args.private_output_root)
            if output.exists():
                raise ValueError("output already exists")
            facts = export_facts(intake, args.audience)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1
        print(f"Wrote reviewed fact export: {args.output}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
