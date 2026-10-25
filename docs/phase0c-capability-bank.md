# Phase 0C: private capability bank

Phase 0C consolidates statements from candidate-authorised CV versions into a reusable, private capability catalogue. It does not convert a CV statement into verified evidence or grant permission to publish it. The Phase 0A dataset and Phase 0B1 intake remain separate and unchanged.

## Inputs and outputs

`build-bank` reads only the source paths explicitly passed to it. It does not scan for other documents. An editorial JSON seed supplies stable `cap-...` IDs, categories, interpretation labels, source ID and paragraph references, candidate-review questions and optional application-oriented wording. The command re-ingests the passed sources locally, checks every source reference, and creates private reports in an empty, Git-ignored output directory or an explicit private root outside Git.

```sh
python -m cvwizard build-bank sources_private/version-a.docx sources_private/version-b.docx \
  --seed data/private/capability-seed.json \
  --old-intake data/private/phase0b1-intake.yaml \
  --output-dir data/private/phase0c
```

The seed and generated bank are private if they contain candidate material. Never commit them. The generator refuses to replace existing files. Source IDs are SHA-256-derived as in Phase 0B1. A bank entry stores original CV text, paragraph location, assertion ID and source ID. `explicit_vs_interpreted` distinguishes a directly stated capability from an editorial interpretation; `interpretation_note` is mandatory for the latter. Every alternative description is labelled `PROPOSED_WORDING` and cites a subset of that competency's source references. `CV_DERIVED` is the only status accepted by the generator. Candidate review and independent evidence verification require separate human-controlled processes.

Default categories cover process engineering, simulation, data science, industrial AI, project delivery, research, teaching, collaboration, software and qualifications. The seed may declare `additional_categories`. No proficiency level or seniority is generated from keywords. Keep distinct work and contribution scopes separate; group paraphrases of the same underlying capability under one stable competency ID. Multiple mentions in tailored CVs are not independent confirmation.

The outputs are `01_source_inventory.md`, `02_master_capability_bank.json`, `03_capability_catalogue.md`, `04_semantic_mapping.md`, `05_coverage_summary.md`, `06_candidate_review_queue.md` and `assertion_id_migration.json`. The Phase 1 interface is specified separately in [phase1-job-fit-interface.md](phase1-job-fit-interface.md). The inventory reports only the explicitly supplied versions and records known missing versions from the seed. It must not imply completeness beyond the authorised collection.

## DOCX correction and assertion IDs

DOCX extraction now emits `\t` for `w:tab` and `\n` for `w:br` and `w:cr`, preserving their order within a paragraph. The paragraph number and document SHA-256 remain stable. Phase 0B1 assertion IDs hash whitespace-normalised paragraph text; adding a previously lost separator can change an ID where text was formerly joined. The `--old-intake` option maps old and new IDs by unchanged source ID and paragraph location. Review any missing mapping manually. Do not replace the earlier intake or silently rewrite its review history.

The parser remains literal. It does not interpret visual layout, tables, tracked changes, OCR, or semantic sections. The bank needs candidate review to resolve attribution, metrics, qualification status, publication claims, confidentiality and permitted wording. See [Phase 1 interface](phase1-job-fit-interface.md) for how later job-fit assessment should consume this unverified bank.
