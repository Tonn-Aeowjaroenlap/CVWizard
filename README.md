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
