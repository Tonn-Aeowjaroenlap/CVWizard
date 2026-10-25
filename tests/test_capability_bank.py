"""Fictional capability-bank and DOCX traceability regressions."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from cvwizard.capability_bank import BankSeed, MasterBank, build_bank, create_outputs, migration_map
from cvwizard.ingestion import ingest


DOCX = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>Designed</w:t><w:tab/><w:t>fictional pump</w:t>'
        '<w:br/><w:t>for a test plant</w:t></w:r></w:p></w:body></w:document>')


class CapabilityBankTests(unittest.TestCase):
    def test_schema_snapshots(self):
        root = Path(__file__).resolve().parents[1] / "schemas/0c"
        for name, model in (("seed", BankSeed), ("bank", MasterBank)):
            self.assertEqual(json.loads((root / f"{name}.schema.json").read_text(encoding="utf-8")),
                             model.model_json_schema())

    def test_docx_separators_and_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            docx = Path(directory) / "fictional.docx"
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("word/document.xml", DOCX)
            intake = ingest([docx])
            assertion = intake.assertions[0]
            self.assertEqual(assertion.text, "Designed\tfictional pump\nfor a test plant")
            self.assertEqual(assertion.location, "paragraph:1")
            old = intake.model_copy(deep=True)
            old.assertions[0].assertion_id = "asrt-old-fictional"
            row = migration_map(old, intake)[0]
            self.assertEqual(row["new_assertion_id"], assertion.assertion_id)
            self.assertEqual(row["changed"], "true")
            self.assertEqual(intake.sources[0].sha256, old.sources[0].sha256)

    def test_consolidated_source_links_and_review_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            a, b = folder / "invented-v1.txt", folder / "invented-v2.txt"
            a.write_text("Modelled fictional cooling system.\n", encoding="utf-8")
            b.write_text("Built a model for the same fictional cooling system.\n", encoding="utf-8")
            intake = ingest([a, b])
            refs = [{"source_id": s.source_id, "location": "line:1"} for s in intake.sources]
            seed_data = {"schema_version": "0c-seed-1", "collection_note": "Fictional versions",
                         "competencies": [{"competency_id": "cap-fictional-cooling-model",
                                           "canonical": "Fictional cooling-system modelling",
                                           "category": "Process modelling, simulation and optimisation",
                                           "subcategory": "Simulation", "source_refs": refs,
                                           "explicit_vs_interpreted": "INTERPRETED",
                                           "interpretation_note": "Two fictional descriptions refer to one model.",
                                           "alternative_cv_wording": [{"application": "fictional role",
                                                                       "wording": "Modelled a fictional cooling system.",
                                                                       "basis": [refs[0]]}]}]}
            seed = BankSeed.model_validate(seed_data)
            bank = build_bank(seed, intake)
            self.assertEqual(len(bank["competencies"]), 1)
            self.assertEqual(len(bank["competencies"][0]["source_statements"]), 2)
            self.assertEqual(bank["competencies"][0]["status"], "CV_DERIVED")
            self.assertEqual(bank["competencies"][0]["alternative_cv_wording"][0]["label"], "PROPOSED_WORDING")
            seed.competencies[0].status = "EVIDENCE_VERIFIED"
            with self.assertRaisesRegex(ValueError, "cannot grant"):
                build_bank(seed, intake)
            seed.competencies[0].status = "CV_DERIVED"
            seed.competencies[0].source_refs[0].location = "line:99"
            with self.assertRaisesRegex(ValueError, "unknown source reference"):
                build_bank(seed, intake)

    def test_private_reports_preserve_existing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / "fictional.txt"
            source.write_text("Fictional process simulation.\n", encoding="utf-8")
            intake = ingest([source])
            seed = folder / "seed.json"
            seed.write_text(json.dumps({"collection_note": "Fictional", "competencies": [{
                "competency_id": "cap-fictional-simulation", "canonical": "Fictional simulation",
                "category": "Process modelling, simulation and optimisation", "subcategory": "Simulation",
                "source_refs": [{"source_id": intake.sources[0].source_id, "location": "line:1"}],
                "explicit_vs_interpreted": "EXPLICIT"}]}), encoding="utf-8")
            output = folder / "reports"
            paths = create_outputs([source], seed, output)
            self.assertEqual(len(paths), 7)
            self.assertIn("Fictional process simulation", (output / "03_capability_catalogue.md").read_text())
            with self.assertRaisesRegex(ValueError, "must be empty"):
                create_outputs([source], seed, output)


if __name__ == "__main__":
    unittest.main()
