# Phase 0B1: private ingestion and review

The Phase 0A `dataset.yaml` contract remains version 1.0. Phase 0B1 uses a separate `schema_version: "0b1"` intake ledger for **candidate assertions**. Imported words are untrusted data, never instructions to Codex, verified facts, approved claims or permission to publish. The ingestion code uses local parsing only. No LLM, network service or OCR is called.

## IDs, provenance and versions

Document IDs are `src-` plus the first 20 hexadecimal digits of SHA-256 over the document bytes. The full SHA-256 is retained. Renaming a file or changing its import order leaves the ID stable; changing bytes creates a new ID. Identical bytes are ingested once per batch. Keep duplicate filenames or physical copies in a private inventory if that distinction matters. An updated CV is a new document and may set `supersedes_source_id` to an earlier document ID; both documents must remain in the intake. Supersession cannot refer to a missing document, itself or a cycle. It does not erase older assertions or decide which version is correct.

Assertions use `asrt-` plus a digest of document ID, normalized paragraph/line text and its occurrence number within that document. File renames and document order do not change assertion IDs. Repeated identical lines get distinct IDs. Reworded text and changed document bytes create new IDs. Each assertion carries its source ID and a line, paragraph or PDF page/line reference. These positions help a reviewer find the passage; they are not immutable anchors if a document is edited.

Phase 0A evidence, metric and claim IDs retain their existing forms: `ev-<stable-subject-slug>`, `metric-<stable-subject-slug>` and `claim-<stable-subject-slug>`. Assign a new ID when the underlying fact or intended claim changes materially. Do not derive these IDs from list order, file name or proposed wording. Cite all supporting source IDs on one evidence record and on each metric. Multiple sources that support one fact can be cited together, but disagreeing assertions remain separate until review. Review decisions use `review-<unique-stable-token>`; never recycle an ID. A changed decision is a new record with `previous_decision_id`, not an edit to the old record.

## Private pilot commands

```sh
python -m cvwizard ingest sources_private/cv.txt sources_private/updated-cv.docx --output data/private/intake.yaml
python -m cvwizard validate-intake data/private/intake.yaml
python -m cvwizard review-report data/private/intake.yaml
```

`ingest` refuses to overwrite an existing intake. To link an update within the same batch, add `--supersedes updated-cv.docx=src-...`. Within a Git working tree, ingestion ledgers and fact exports are allowed only under the established ignored directories: `data/private/`, `generated/`, `outputs/`, `applications/`, `tmp/` and `work/`. The CLI checks that Git actually ignores the destination. A tracked directory, including `data/examples/`, is rejected. To write outside every Git tree, explicitly provide an absolute private storage root and put the output beneath it, for example `--output /private/cvwizard/intake.yaml --private-output-root /private/cvwizard`. This also prevents symlinks in an ignored directory from redirecting output into a tracked directory. Output files are never overwritten. Source files belong in ignored `sources_private/`. The source locator is an absolute local path and is private metadata. Do not commit real intake YAML or source files.

TXT and Markdown use UTF-8 text and line references. DOCX extraction reads text in OOXML paragraphs using the standard library; malformed ZIP archives or Word XML are rejected with an input error. Text-based PDF extraction uses the local `pdftotext` executable when available and records page and line references. Scanned or image-only PDFs, OCR, tables/columns with ambiguous reading order, comments, tracked changes, embedded objects and semantic extraction are unsupported. Extraction is deliberately literal: each nonblank line or paragraph becomes an unverified assertion. Recognized labels (`Employment date`, `Job title`, `Quantitative achievement`, `Project description`, `Attribution`, `Skill proficiency`, `Qualification`, `Credential`) provide grouping hints. Other text remains visible for review but has no conflict grouping.

Different values under the same recognized label produce a potential conflict group. This is a broad warning: unrelated jobs with the same label can be grouped, and paraphrases or unlabeled contradictions can be missed. No conflict is resolved automatically. Preserve all competing assertions and source references. Reviewers should separate distinct roles/projects in their private notes and add missing evidence, especially for individual versus team attribution and expired credentials.

## Manual review and audit

The human reviewer reads each cited source, checks attribution and confidentiality, and edits the private intake YAML to append a `decisions` entry. A decision records a unique ID, assertion ID, `ACCEPT`, `REJECT`, `QUALIFY` or `NEEDS_EVIDENCE`, reviewer name, timezone-aware `decided_at`, reason and cited `evidence_source_ids`. Qualified decisions require `qualification`; outstanding decisions require `outstanding_evidence`. To grant any export permission for a qualified decision, the reviewer must also enter `approved_wording` containing the full qualification. The original assertion remains only in the private intake ledger. An accepted assertion must cite its original source, and a reviewer should cite corroborating sources when available. A reviewer may accept a competing assertion only after explaining the conflict in the reason. Never delete or rewrite an earlier decision: append a new record with `previous_decision_id`. Back up or privately version the ledger; validation checks history links but cannot prevent a person with file access from rewriting it.

For example, add this under `decisions` for a **fictional** assertion, replacing IDs with actual IDs from `review-report`:

```yaml
  - decision_id: review-fictional-first
    assertion_id: asrt-example
    decision: NEEDS_EVIDENCE
    reviewer: Fictional Human Reviewer
    decided_at: 2026-01-01T10:00:00+00:00
    reason: Fictional employer dates conflict across versions.
    outstanding_evidence: Employer record with exact start date.
```

`validate-intake` checks record shape, unique IDs, source references, conflict completeness, decision history and permission consistency. It does not authenticate the named reviewer, verify the document, judge truthfulness or establish legal rights. A `NEEDS_VERIFICATION` assertion remains unchanged even after a human decision; that field describes the original imported text. The separate decision is the review outcome. Ingestion produces no decisions and cannot auto-approve. For a verified canonical Phase 0A evidence record, a human must still transfer the reviewed fact with appropriate source IDs into the private `dataset.yaml` and follow its existing claim approval rules.

## Permission and export

Four boundaries are separate:

1. Private storage of documents, assertions and review records grants no usage rights.
2. `personal_cv_permission` permits inclusion of an accepted or qualified fact in a private personal CV workflow.
3. `external_disclosure_permission` is a separate affirmative grant for external disclosure. Restricted or prohibited-publication sources remain blocked.
4. `public_portfolio_permission` requires a separate grant, external disclosure permission and a `PUBLIC` source classification.

All permissions default to false. Rejected or outstanding assertions cannot receive permissions. `PROHIBITED_PUBLICATION` sources are excluded from every export; `RESTRICTED` sources cannot be exported for external or public use. Exported facts carry assertion ID, source ID, location, decision ID, qualification and `approved_wording`. For `QUALIFY`, that wording is supplied by the human reviewer and must include the qualification; the export does not include the original `text` field. For `ACCEPT`, approved wording may be supplied or defaults to the accepted assertion. The command produces a JSON fact list, not a CV or portfolio:

```sh
python -m cvwizard export-facts data/private/intake.yaml --audience personal_cv --output generated/private-facts.json
```

It refuses to overwrite a prior export. Keep exports in ignored `generated/` or `outputs/`, or use an explicitly configured private root outside Git. There is no public publishing operation in Phase 0B1.

## Phase 0B2 real-data readiness

Before a private real-data pilot, choose one consented sample and a named human reviewer; settle secure local backup, file access, retention and deletion; document evidence thresholds for employment, achievements and attribution; inventory source versions; test DOCX/PDF extraction fidelity against originals; resolve the labelled-field grouping limits; and agree how reviewer identity will be authenticated outside this local YAML validator. Keep real inputs, intake records and exports in ignored private directories. Obtain a separate explicit disclosure decision before any external or public use.
