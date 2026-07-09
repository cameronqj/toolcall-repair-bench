# Contributing

`toolcall-repair-bench` is a benchmark, not a tool. It measures how well repair libraries recover the tool call a local model meant to make from the malformed output it actually emitted. Contributions are real cases, thin adapters, and fixes to the scorer or docs, kept narrow on purpose. Before you start, read [`docs/constitution.md`](docs/constitution.md); it sets the rules the rest of this file enforces.

## Development Setup

```bash
python3 -m pip install -e ".[dev]"
make test
make lint
```

## Useful Commands

- `make validate` — check every case against the corpus schema.
- `make score` — run all available adapters over the offline corpus.
- `make leaderboard` — regenerate the leaderboard table in the README.

## Add A Case

A case is a real raw model output plus a gold answer. To add one:

- Record provenance: which model produced the output and how it was captured. A case with no provenance is not accepted.
- Sanitize it. Confirm the `raw_output` contains no secrets, no credentials, no local paths, and no private source. Captured output can carry any of these by accident.
- Justify the gold label. The gold answer must be defensible from the `raw_output` alone. If the case is genuinely ambiguous, add a `note` explaining the call rather than guessing.
- Check for duplicates. Make sure the case is not a near-copy of one already in the corpus.

## Add An Adapter

An adapter wraps an upstream repair library so the benchmark can score it. To add one:

- Import, don't reimplement. The adapter calls the upstream library; it does not fork or copy that library's parser into this repo.
- Stay offline. No network and no GPU in the offline scoring path. If the upstream cannot be imported, report the adapter unavailable.
- Be deterministic. The same input must produce the same output every run.

## Pull Request Checklist

- The scorer is green in CI.
- The leaderboard is regenerated and committed (`make leaderboard`).
- `make test` and `make lint` pass.
- No secrets or local paths appear in any case.
- Commits are signed off with DCO (`git commit -s`).

## Scope Boundaries

What this project will and will not become is set in [`docs/constitution.md`](docs/constitution.md) and the ADRs under [`docs/adr/`](docs/adr/). In short: this is a dataset and a scorer, not a tool, router, or agent; no entrant is privileged; adapters import rather than fork. If a change pushes against those boundaries, raise it as an issue first.
