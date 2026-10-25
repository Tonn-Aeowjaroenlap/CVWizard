"""Synthetic-only end-to-end intake and privacy tests."""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from cvwizard.ingestion import ingest
from cvwizard.models import Confidentiality
from cvwizard.output_policy import private_output_path
from cvwizard.review import DecisionKind, ReviewDecision, export_facts, load_intake, validate_intake


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/examples/sources"
V1 = SOURCES / "fictional_cv_v1.txt"
V2 = SOURCES / "fictional_cv_v2.md"


class IngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.intake = ingest([V1, V2])

    def test_conflicts_provenance_duplicates_and_rename(self) -> None:
        self.assertEqual(len(self.intake.sources), 2)
        self.assertEqual(len(self.intake.conflicts), 7)
        self.assertEqual(len(self.intake.assertions), 17)
        self.assertFalse(self.intake.decisions)
        self.assertTrue(all(a.verification_status == "NEEDS_VERIFICATION" for a in self.intake.assertions))
        self.assertTrue(all(a.location.startswith("line:") for a in self.intake.assertions))
        self.assertEqual(len(ingest([V1, V1]).sources), 1)
        linked = ingest([V1, V2], supersedes={V2.name: self.intake.sources[0].source_id})
        self.assertEqual(linked.sources[1].supersedes_source_id, self.intake.sources[0].source_id)
        with tempfile.TemporaryDirectory() as directory:
            renamed = Path(directory) / "renamed.txt"
            renamed.write_bytes(V1.read_bytes())
            self.assertEqual(ingest([renamed]).sources[0].source_id, self.intake.sources[0].source_id)
            self.assertEqual(ingest([renamed]).assertions[0].assertion_id, self.intake.assertions[0].assertion_id)
        self.assertEqual(validate_intake(self.intake), [])

    def test_review_history_and_export_gates(self) -> None:
        assertion = next(a for a in self.intake.assertions if a.field == "job title")
        source = assertion.source_id
        decision = ReviewDecision(
            decision_id="review-first", assertion_id=assertion.assertion_id,
            decision=DecisionKind.QUALIFY, reviewer="Fictional Human Reviewer",
            decided_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            reason="Fictional employer record cited for pilot", evidence_source_ids=[source],
            qualification="Role title needs employer confirmation", personal_cv_permission=True,
            approved_wording="Reliability Engineer; role title needs employer confirmation",
        )
        self.intake.decisions.append(decision)
        self.assertEqual(validate_intake(self.intake), [])
        facts = export_facts(self.intake, "personal_cv")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["approved_wording"], decision.approved_wording)
        self.assertNotIn("text", facts[0])
        self.assertIn(assertion.text, [a.text for a in self.intake.assertions])
        self.assertEqual(export_facts(self.intake, "external"), [])
        self.assertEqual(export_facts(self.intake, "public"), [])
        self.intake.decisions.append(ReviewDecision(
            decision_id="review-reversed", assertion_id=assertion.assertion_id,
            decision=DecisionKind.REJECT, reviewer="Fictional Human Reviewer",
            decided_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            reason="Fictional follow-up found no supporting employer record",
            previous_decision_id="review-first",
        ))
        self.assertEqual(export_facts(self.intake, "personal_cv"), [])
        self.assertEqual(validate_intake(self.intake), [])
        broken = copy.deepcopy(self.intake)
        broken.decisions[1].previous_decision_id = None
        self.assertIn("broken decision history", "\n".join(validate_intake(broken)))

    def test_rejects_unsupported_approval_and_conflict_tampering(self) -> None:
        assertion = self.intake.assertions[0]
        base = dict(
            decision_id="review-invalid", assertion_id=assertion.assertion_id,
            reviewer="Fictional Reviewer", decided_at=datetime.now(timezone.utc), reason="test",
        )
        with self.assertRaisesRegex(ValueError, "cited evidence"):
            ReviewDecision(decision=DecisionKind.ACCEPT, **base)
        with self.assertRaisesRegex(ValueError, "usage permission"):
            ReviewDecision(decision=DecisionKind.REJECT, personal_cv_permission=True, **base)
        with self.assertRaisesRegex(ValueError, "qualification"):
            ReviewDecision(decision=DecisionKind.QUALIFY, evidence_source_ids=[assertion.source_id], **base)
        with self.assertRaisesRegex(ValueError, "human-approved wording"):
            ReviewDecision(decision=DecisionKind.QUALIFY, evidence_source_ids=[assertion.source_id],
                           qualification="fictional limit", personal_cv_permission=True, **base)
        with self.assertRaisesRegex(ValueError, "include the qualification"):
            ReviewDecision(decision=DecisionKind.QUALIFY, evidence_source_ids=[assertion.source_id],
                           qualification="fictional limit", approved_wording="Unqualified claim",
                           personal_cv_permission=True, **base)
        self.intake.conflicts = []
        self.assertIn("conflict report does not match", "\n".join(validate_intake(self.intake)))
        with self.assertRaisesRegex(ValueError, "invalid intake"):
            export_facts(self.intake, "personal_cv")

    def test_public_export_needs_explicit_permission_and_public_source(self) -> None:
        assertion = self.intake.assertions[0]
        self.intake.decisions.append(ReviewDecision(
            decision_id="review-public", assertion_id=assertion.assertion_id,
            decision=DecisionKind.ACCEPT, reviewer="Fictional Reviewer",
            decided_at=datetime.now(timezone.utc), reason="Fictional pilot approval",
            evidence_source_ids=[assertion.source_id], external_disclosure_permission=True,
            public_portfolio_permission=True,
        ))
        self.assertEqual(export_facts(self.intake, "public"), [])
        source = self.intake.sources[0]
        source.confidentiality = Confidentiality.PUBLIC
        self.assertEqual(len(export_facts(self.intake, "public")), 1)
        source.confidentiality = Confidentiality.RESTRICTED
        self.assertEqual(export_facts(self.intake, "external"), [])

    def test_docx_pdf_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            docx = folder / "fictional.docx"
            with zipfile.ZipFile(docx, "w") as archive:
                archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Job title: Invented Tester</w:t></w:r></w:p></w:body></w:document>')
            self.assertEqual(ingest([docx]).assertions[0].location, "paragraph:1")
            output = folder / "intake.yaml"
            run = subprocess.run([sys.executable, "-m", "cvwizard", "ingest", str(V1), str(V2), "--output", str(output),
                                  "--private-output-root", directory], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            parsed, errors = load_intake(output)
            self.assertEqual(errors, [])
            self.assertIsNotNone(parsed)
            report = subprocess.run([sys.executable, "-m", "cvwizard", "review-report", str(output)], capture_output=True, text=True)
            self.assertIn("CONFLICT job title", report.stdout)
            facts = folder / "facts.json"
            run = subprocess.run([sys.executable, "-m", "cvwizard", "export-facts", str(output), "--audience", "public", "--output", str(facts),
                                  "--private-output-root", directory], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(json.loads(facts.read_text()), [])
            pdf = folder / "empty.pdf"
            pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
            with self.assertRaises(ValueError):
                ingest([pdf])

    def test_fictional_review_fixture(self) -> None:
        intake, errors = load_intake(ROOT / "data/examples/reviewed-intake.yaml")
        self.assertEqual(errors, [])
        self.assertIsNotNone(intake)
        facts = export_facts(intake, "personal_cv")
        self.assertEqual(len(facts), 2)
        qualified = next(f for f in facts if f["qualification"])
        self.assertIn(qualified["qualification"].casefold(), qualified["approved_wording"].casefold())
        self.assertNotIn("text", qualified)
        self.assertEqual(export_facts(intake, "public"), [])

    def test_output_path_policy_and_cli_rejections(self) -> None:
        ignored = ROOT / "data/private/policy-test.yaml"
        self.assertEqual(private_output_path(ignored), ignored)
        tracked = ROOT / "data/examples/accidental-private.yaml"
        with self.assertRaisesRegex(ValueError, "unsafe output path"):
            private_output_path(tracked)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            outside = folder / "intake.yaml"
            with self.assertRaisesRegex(ValueError, "requires --private-output-root"):
                private_output_path(outside)
            self.assertEqual(private_output_path(outside, folder), outside)
            with self.assertRaisesRegex(ValueError, "outside configured private root"):
                private_output_path(folder.parent / "elsewhere.yaml", folder)
            command = [sys.executable, "-m", "cvwizard", "ingest", str(V1), "--output"]
            result = subprocess.run(command + [str(tracked)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unsafe output path", result.stdout)
            self.assertFalse(tracked.exists())
            result = subprocess.run(command + [str(outside)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires --private-output-root", result.stdout)
            review_fixture = ROOT / "data/examples/reviewed-intake.yaml"
            result = subprocess.run([sys.executable, "-m", "cvwizard", "export-facts", str(review_fixture),
                                     "--audience", "personal_cv", "--output", str(folder / "facts.json")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires --private-output-root", result.stdout)
            result = subprocess.run([sys.executable, "-m", "cvwizard", "export-facts", str(review_fixture),
                                     "--audience", "personal_cv", "--output", str(tracked)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("unsafe output path", result.stdout)
            self.assertFalse(tracked.exists())
        with tempfile.TemporaryDirectory(dir=ROOT / "data/private") as directory:
            link = Path(directory) / "alias"
            link.symlink_to(ROOT / "data/examples", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsafe output path"):
                private_output_path(link / "leak.yaml")

    def test_malformed_docx_and_supersession_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            bad_zip = folder / "bad.docx"
            bad_zip.write_bytes(b"not a ZIP archive")
            with self.assertRaisesRegex(ValueError, "DOCX archive or document XML is invalid"):
                ingest([bad_zip])
            missing_xml = folder / "missing.docx"
            with zipfile.ZipFile(missing_xml, "w") as archive:
                archive.writestr("other.xml", "<root/>")
            with self.assertRaisesRegex(ValueError, "DOCX archive or document XML is invalid"):
                ingest([missing_xml])
            invalid_xml = folder / "invalid.docx"
            with zipfile.ZipFile(invalid_xml, "w") as archive:
                archive.writestr("word/document.xml", "<broken")
            with self.assertRaisesRegex(ValueError, "DOCX archive or document XML is invalid"):
                ingest([invalid_xml])
            wrong_xml = folder / "wrong.docx"
            with zipfile.ZipFile(wrong_xml, "w") as archive:
                archive.writestr("word/document.xml", "<root/>")
            with self.assertRaisesRegex(ValueError, "lacks a Word document body"):
                ingest([wrong_xml])
        with self.assertRaisesRegex(ValueError, "input filename not provided"):
            ingest([V1, V2], supersedes={"mistyped.docx": self.intake.sources[0].source_id})
        first, second = self.intake.sources
        first.supersedes_source_id = first.source_id
        self.assertIn("cannot supersede itself", "\n".join(validate_intake(self.intake)))
        first.supersedes_source_id = second.source_id
        second.supersedes_source_id = first.source_id
        self.assertIn("cyclic supersession", "\n".join(validate_intake(self.intake)))
        second.supersedes_source_id = "src-nonexistent"
        self.assertIn("unknown superseded source", "\n".join(validate_intake(self.intake)))

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext is optional")
    def test_text_pdf_extraction(self) -> None:
        # A minimal fictional text PDF assembled locally, with no PDF dependency.
        stream = b"BT /F1 12 Tf 72 720 Td (Job title: Invented Tester) Tj ET\n"
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
        ]
        content = b"%PDF-1.4\n"
        offsets = [0]
        for number, obj in enumerate(objects, 1):
            offsets.append(len(content))
            content += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref = len(content)
        content += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
        content += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:])
        content += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fictional.pdf"
            path.write_bytes(content)
            assertion = ingest([path]).assertions[0]
            self.assertEqual(assertion.field, "job title")
            self.assertTrue(assertion.location.startswith("page:1/line:"))


if __name__ == "__main__":
    unittest.main()
