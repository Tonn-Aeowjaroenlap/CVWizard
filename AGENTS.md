# CVWizard repository instructions

- Phase 0A stores career facts as versioned YAML evidence, sources and claims. CVs and application text are derived outputs.
- Keep Python 3.11+ code small, typed and offline. Run `python -m unittest discover -s tests -v` and validate the fictional fixture before committing.
- Cite source IDs for every evidence record and metric. Preserve individual, team and programme scope. Never invent facts, numbers, provenance or approvals.
- Keep interpretations and proposed wording in the claims ledger. Unknown, conflicting, unsupported and prohibited claims cannot be auto-approved. A human must verify and grant usage permission before an approved statement is used.
- Commit only clearly fictional examples. Put actual career records in `data/private/`, source documents in `sources_private/`, and generated application files in ignored output directories. Never commit credentials or confidential material.
- Automation may parse, validate and report errors. It must not infer personal attribution, clear confidentiality restrictions, submit applications, or mark claims approved for a human.
