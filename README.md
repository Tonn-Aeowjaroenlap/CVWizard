# CVWizard

CVWizard is an evidence-grounded career intelligence project. Phase 0A provides a local, offline foundation for structured career records and a claims ledger. All checked-in career data is explicitly fictional. No LLM service, paid API or network call is needed for validation.

## Start

Python 3.11 or newer is required.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m cvwizard validate data/examples/dataset.yaml
python -m unittest discover -s tests -v
```

`validate` accepts a YAML file or a directory containing `dataset.yaml`. It prints errors and exits with status 1 for an invalid dataset. The installed `cvwizard validate` command does the same. Use `mkdir -p data/private sources_private` if those directories are absent in a fresh checkout; their contents are ignored by Git.

## Data boundary

`data/examples/dataset.yaml` contains invented people, organisations and metrics. Real candidate records belong in `data/private/`; original CVs and other source documents belong in `sources_private/`. Generated CVs, applications and exports belong in ignored `generated/`, `outputs/` or `applications/`. Check `git status` before every commit. Never copy private material into `data/examples/` or public portfolio material without explicit review.

Existing CVs can supply leads for evidence collection, but their claims are not automatically verified. The approved claims ledger is distinct from verified source material; neither a source's verification nor a generated sentence grants permission to publish.

See [architecture](docs/architecture.md), [roadmap](docs/roadmap.md) and the [v1 YAML schema](schemas/v1/dataset.schema.yaml).

## Phase 0B1 fictional pilot

```sh
python -m cvwizard ingest data/examples/sources/fictional_cv_v1.txt data/examples/sources/fictional_cv_v2.md --output data/private/pilot-intake.yaml
python -m cvwizard validate-intake data/private/pilot-intake.yaml
python -m cvwizard review-report data/private/pilot-intake.yaml
```

The fictional documents intentionally disagree. Import creates only unverified assertions and potential conflict groups. [The fictional review ledger](data/examples/reviewed-intake.yaml) shows accepted, rejected, qualified and outstanding decisions and an approval change. Human review, audit entries, permission controls, format limits and a private real-data pilot checklist are described in [ingestion and review](docs/ingestion-and-review.md). `export-facts` writes only explicitly permitted reviewed facts to a local JSON file; it does not create a CV or publish anything.

Private CLI outputs must go to established Git-ignored directories or under an explicit absolute `--private-output-root` outside Git. Qualified exports require reviewer-approved wording that includes the qualification.

## Phase 0C capability bank

Phase 0C consolidates explicitly supplied, candidate-authorised CV versions into a private, source-linked capability bank. A curated seed groups overlapping statements and records interpretations and review questions. The generator does not verify facts or approve wording. See [the Phase 0C guide](docs/phase0c-capability-bank.md) and [Phase 1 job-fit interface](docs/phase1-job-fit-interface.md).
