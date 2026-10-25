"""Offline tests using only invented records."""

from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from cvwizard.models import CareerDataset
from cvwizard.validation import validate_path


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "data/examples/dataset.yaml"


class DatasetValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))

    def check_invalid(self, change, expected: str) -> None:
        data = copy.deepcopy(self.raw)
        change(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.yaml"
            path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            errors = validate_path(path)
        self.assertTrue(errors, "invalid dataset passed")
        self.assertIn(expected, "\n".join(errors))

    def test_fictional_example_and_schema_snapshot(self) -> None:
        self.assertEqual(validate_path(EXAMPLE), [])
        self.assertEqual(
            yaml.safe_load((ROOT / "schemas/v1/dataset.schema.yaml").read_text(encoding="utf-8")),
            CareerDataset.model_json_schema(),
        )

    def test_structural_failures(self) -> None:
        cases = [
            (lambda d: d.update(schema_version="2.0"), "schema_version"),
            (lambda d: d["evidence"][0].update(category="UNKNOWN"), "category"),
            (lambda d: d["evidence"][0].update(verification_status="MAYBE"), "verification_status"),
            (lambda d: d["sources"][0].update(provenance=""), "provenance"),
            (lambda d: d["sources"][0].pop("locator"), "locator"),
            (lambda d: d["sources"][2].update(qualifications=[]), "qualified source verification"),
            (lambda d: d["evidence"][0].update(source_ids=[]), "source_ids"),
            (lambda d: d["evidence"][4]["metrics"][0].update(value="unknown"), "value"),
            (lambda d: d["evidence"][4]["metrics"][0].update(unit=""), "unit"),
            (lambda d: d["evidence"][0].update(end_date="2010-01-01"), "end_date precedes"),
        ]
        for change, expected in cases:
            with self.subTest(expected=expected):
                self.check_invalid(change, expected)

    def test_cross_record_failures(self) -> None:
        cases = [
            (lambda d: d["evidence"][1].update(evidence_id="ev-education"), "duplicate evidence_id"),
            (lambda d: d["sources"][1].update(source_id="src-individual-review"), "duplicate source_id"),
            (lambda d: d["claims"][0].update(supporting_evidence_ids=["ev-missing"]), "missing evidence"),
            (lambda d: d["evidence"][0].update(source_ids=["src-missing"]), "missing source"),
            (lambda d: d["evidence"][4]["metrics"][0].update(scope="PROGRAMME"), "scope differs"),
            (lambda d: d["claims"][2].update(contribution_scope="INDIVIDUAL"), "PROGRAMME scope"),
            (lambda d: d["evidence"][4]["metrics"][0].update(source_ids=["src-team-report"]), "not cited by evidence"),
        ]
        for change, expected in cases:
            with self.subTest(expected=expected):
                self.check_invalid(change, expected)

    def test_approval_boundaries(self) -> None:
        def approve(data, index: int) -> None:
            data["claims"][index].update(
                approval_status="APPROVED", usage_permission="GRANTED",
                approved_statement=data["claims"][index]["proposed_statement"],
                approved_by="Fictional Reviewer", approved_on="2026-01-01",
            )

        cases = [
            (lambda d: approve(d, 3), "NEEDS_VERIFICATION claim cannot be approved"),
            (lambda d: approve(d, 4), "UNSUPPORTED claim cannot be approved"),
            (lambda d: approve(d, 5), "PROHIBITED claim cannot be approved"),
            (lambda d: d["claims"][0].update(usage_permission="NOT_REQUESTED"), "GRANTED usage_permission"),
            (lambda d: d["claims"][0].pop("approved_by"), "approval requires"),
            (lambda d: d["claims"][2].update(required_qualifications=[]), "missing mandatory qualifications"),
            (lambda d: d["claims"][2].update(approved_statement="Downtime fell by 8.5%."), "omits qualification"),
            (lambda d: d["sources"][0].update(verification_status="NEEDS_VERIFICATION"), "source src-individual-review is not verified"),
            (lambda d: d["evidence"][4].update(confidentiality="PROHIBITED_PUBLICATION"), "prohibits publication"),
        ]
        for change, expected in cases:
            with self.subTest(expected=expected):
                self.check_invalid(change, expected)

    def test_yaml_duplicate_keys_and_cli_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dataset.yaml"
            path.write_text('schema_version: "1.0"\nschema_version: "2.0"\n', encoding="utf-8")
            self.assertIn("duplicate YAML key", "\n".join(validate_path(path)))
            invalid = subprocess.run(
                [sys.executable, "-m", "cvwizard", "validate", str(path)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(invalid.returncode, 1)
            self.assertIn("ERROR:", invalid.stdout)
        valid = subprocess.run(
            [sys.executable, "-m", "cvwizard", "validate", str(EXAMPLE)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(valid.returncode, 0, valid.stderr + valid.stdout)


if __name__ == "__main__":
    unittest.main()
