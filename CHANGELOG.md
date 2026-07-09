# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Semver applies to **corpus releases** too: the offline corpus carries its own
version line, and breaking changes to the case schema or to gold labels are
major bumps, additive cases are minor, and fixes are patches.

## [Unreleased]

## [0.1.0] - 2026-06-14

First public release — a precision-first static benchmark for tool-call repair
and abstention behavior on a small, curated, offline corpus. Scores characterize
this corpus only; it is a seed benchmark, not a definitive or industry-standard
one, and it does not run models or execute recovered calls.

### Corpus

- Ships **117 cases**: **85 real captured** outputs (a few seed fixtures plus a
  reviewed subset of the 2026-06-14 local Ollama panel — 6 models × 20 prompts)
  and **32 synthetic**, hand-authored cases, including negative controls
  (`0030`–`0037`) that must not be repaired. Every case records an explicit
  `provenance.kind` (`captured` | `synthetic`); `make validate` enforces that
  `kind` is present and self-consistent (the legacy `synthetic` boolean must
  agree, captured cases must name a real model, synthetic cases must set
  `model: "synthetic"`) plus cross-case integrity (unique ids, id-matches-
  filename, gold names that were actually offered).
- Captured coverage is local-Ollama-only and **concentrated by base-model
  family**: the `carnice:9b-q4km` tags (Carnice-9b, a Qwen3.5-9B derivative)
  plus `qwen35:9b-q4km-chat` are ~67% of the captured cases, so per-model and
  per-taxonomy counts are illustrative coverage, not representative weights.
- Three outcome classes the corpus deliberately separates — recoverable
  malformed intent (gold `tool_call`), no-tool natural language (gold
  `no_tool`), and unsafe/ambiguous (gold `no_tool`) — over a closed taxonomy
  enum: `json_in_content`, `toolName_brace_json`, `xml_tool_code`,
  `partial_openai_fields`, `markdown_fenced_json`, `json_with_prose`,
  `python_call_syntax`, `provider_specific`, `prose_false_positive`,
  `plain_answer`, `clarifying_question`, `literal_commands`,
  `code_snippet_mention`, `documentation_example`, `structured_data_no_intent`,
  `missing_required_args`, `ambiguous_tool_choice`, `truncated_tool_call`,
  `unsafe_guessed_intent`, `injection_force_tool`, and
  `unknown_tool_near_match`.
- Raw captures are preserved under `captures/raw/2026-06-14/` for provenance,
  separate from the scored `corpus/cases/`; the panel is documented in
  `docs/captured-model-panel-2026-06-14.md`. A gold label must be defensible
  from `raw_output` alone — a clean, complete, parseable call to an offered tool
  is a recoverable `tool_call` regardless of whether it uses the `arguments` or
  `parameters` key; a missing/empty required argument, an ambiguous choice, or
  adversarial text is `no_tool`.

### Scoring & leaderboard

- Precision-first scoring: unsafe false positives, fabrications, no-tool
  false-positive rate, abstention correctness, recoverable recall, parse /
  name-match / args-exact rates, and **F1 as the last tiebreak** — so a
  maximalist over-repairer (`greedy_name_match`) sorts to the bottom, not the
  top. Output is deterministic (sorted iteration, no clock, no randomness).
- `make leaderboard-check` (run in CI) gates the committed README table and
  `corpus/results.json` against drift, and stays CI-safe without the optional
  proxy installed.

### Package & adapters

- `tcrb` package: adapter protocol + registry, deterministic case loader, schema
  validator, scorer, and leaderboard generator. Adapters receive only the raw
  output and the offered tool names — never the gold label.
- `naive_json` (the dumb floor), `greedy_name_match` (maximalist strawman
  baseline), `local_tool_proxy` (imports the sibling `local-tool-proxy` library
  and degrades to "unavailable" when absent; the checked-in numbers were
  generated with `local-tool-proxy` 0.1.0), plus `litellm`, `ollama_native`, and
  `instructor` stubs.
- Non-network capture scaffold (`tcrb/capture.py`, `make capture-ollama`) that
  emits *pending* captured-case drafts for human review — no auto-labeling, no
  network access, no API keys.

### Docs & hygiene

- `README.md` (claims/non-claims, precision-first reading guide, reproduction
  pinned to `local-tool-proxy` 0.1.0), `EVALUATION.md`, `corpus/README.md`, ADRs
  (`docs/adr/`), `docs/constitution.md`, and the captured-model panel doc.
- Dual licensing: code MIT, corpus CC-BY-4.0. CI runs ruff (`E/W/F/I/B`), schema
  validation, the leaderboard drift gate, and the test suite on Python
  3.9–3.12.

[Unreleased]: https://github.com/cameronqj/toolcall-repair-bench/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/cameronqj/toolcall-repair-bench/releases/tag/v0.1.0
