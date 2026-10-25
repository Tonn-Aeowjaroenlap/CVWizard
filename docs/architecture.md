# Phase 0A architecture

## Data flow

Source documents stay in `sources_private/`. A human or later ingestion workflow records provenance in a private YAML dataset. The `sources`, `evidence` and `claims` sections form a single versioned document. The offline validator checks both record shape and relationships. Any future CV or portfolio text is derived from reviewed claims and kept outside this canonical dataset.

`src/cvwizard/models.py` contains strict Pydantic v2 models. `schemas/v1/dataset.schema.yaml` is the corresponding JSON Schema serialized as YAML for editor and external tooling. The root `schema_version: "1.0"` selects this contract. Unknown fields and schema versions fail validation. `src/cvwizard/validation.py` checks constraints across records. Refresh the schema snapshot after model changes with:

```sh
python -c 'import sys, yaml; from cvwizard.models import CareerDataset; sys.stdout.write(yaml.safe_dump(CareerDataset.model_json_schema(), sort_keys=False))' > schemas/v1/dataset.schema.yaml
```

The schema snapshot is tested against the Python model to catch drift. Cross-record rules remain in Python and are documented here; JSON Schema alone cannot check referenced IDs or human approval.

The project pins Pydantic to 2.13.4 because newer releases can generate a different JSON Schema for the same model and fail the checked-in snapshot test. Revisit the pin and regenerate/review the snapshot as a separate schema maintenance change.

## Evidence model

- `profile` identifies the candidate, separate from evidence.
- `sources` record type, locator, provenance, verification status and confidentiality. A locator may point to a local private file; the checked-in examples use fictional `synthetic://` locators.
- `evidence` uses stable IDs and one of education, employment, project, skill, achievement, publication or certification. Each record has a factual description, context, contribution scope, source IDs, verification status, confidence, confidentiality, and optional dates, metrics, notes and qualifications.
- Metrics have their own ID, finite numeric value, unit, scope, contextual explanation and source IDs. Their scope must match their parent evidence, and cited sources must be present in that evidence.
- `claims` is the proposed wording ledger. Each claim cites evidence IDs and declares attribution scope. Every supporting record must have the same scope. Mixed-scope claims need to be split and reviewed; a programme metric cannot silently become a personal result.

Stable IDs must be unique within their record type. Evidence, source, claim and metric references are checked. Dates must be ordered. YAML duplicate mapping keys are rejected so a later key cannot silently replace an earlier fact. No automatic conflict resolution is attempted.

## Verification and permission lifecycle

`VERIFIED`, `VERIFIED_WITH_QUALIFICATION`, `NEEDS_VERIFICATION`, `CONFLICTING`, `UNSUPPORTED` and `PROHIBITED` describe verification. `approval_status` (`PENDING`, `APPROVED`, `REJECTED`) is a separate editorial decision. `usage_permission` (`NOT_REQUESTED`, `GRANTED`, `DENIED`) records permission to use a claim. Approved claims require verified claim, evidence and source statuses, granted permission, an approved statement, reviewer name and date. Any required qualifications from claim, evidence or source must appear in the ledger and approved statement. Publication-prohibited evidence or sources block approval.

Private or restricted sources may support an approved abstracted claim only after a human grants usage permission. Source documents remain private. Validation checks the presence and consistency of the approval fields; it cannot authenticate a reviewer, inspect the underlying document, determine whether wording is genuinely supported, or establish legal publication rights. Human review remains mandatory.

## V1 workflow and limits

ChatGPT may help reason over user-provided evidence and draft proposed wording. Codex can organize local YAML, run validation and report issues. Neither may turn uncertainty into a verified fact or approve its own claim. The repository has no API, LLM client, scraper, CV generator, database or deployment. A later optional API can read and validate the same versioned dataset and enforce additional access controls without changing the evidence model.

Phase 0B1 adds a separate private intake and review ledger without changing this V1 schema. Read [the ingestion and review workflow](ingestion-and-review.md) for ID conventions, conflict detection, audit records and export boundaries.
