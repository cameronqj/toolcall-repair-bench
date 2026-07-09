# Evaluation methodology

This document explains exactly what `toolcall-repair-bench` measures, what it
does not, and how to reproduce and extend it. It is deliberately conservative:
the corpus is an initial seed, not a definitive benchmark, and the scoring is
designed so that a repairer cannot look good by fabricating calls.

## What the benchmark measures

Given a fixed string a model already emitted (`raw_output`) and the list of
tools that were offered in the request (`request_tools`), a repair adapter must
either recover the intended tool call or abstain. The benchmark scores, per
adapter, over a frozen offline corpus:

- **Repair precision** — of the calls a repairer emits, how many are the right
  call (right name) on a case whose gold is actually a tool call.
- **Recoverable recall** — of the cases whose gold *is* a tool call, how many
  the repairer recovers (right name). This is plain recall, named explicitly so
  it is not confused with "did it do something".
- **No-tool false-positive rate** — of the `no_tool` cases, how often the
  repairer fabricated a call.
- **Unsafe false positives** — fabrications on the unsafe/ambiguous family
  (see [Taxonomy](#case-taxonomy)). These are the worst failures and are read
  first.
- **Abstention correctness** — of the `no_tool` cases, how many the repairer
  correctly left alone.
- **Parse / name / args rates** and **F1** — secondary diagnostics. F1 is a
  tiebreak, never the headline.

## What the benchmark does not measure

- It does **not** run models. It says nothing about how often a given model
  emits a given malformed shape in practice.
- It does **not** measure end-to-end agent task success, multi-turn behavior,
  latency, or tool execution. A repaired call here is never executed.
- It is **not** an industry-standard or definitive benchmark. Scores are only
  meaningful for the included corpus, which is small and mostly synthetic.
- A high F1 is **not** a safety claim. A maximalist repairer can top an F1 table
  by fabricating; precision and the unsafe-FP count are where that shows up.

## Case taxonomy

Every case carries one or more closed-enum `taxonomy` tags describing the
**shape** of the output (not why the model produced it). Tags group into three
outcome classes:

**Recoverable malformed intent** (gold = `tool_call`): a real call emitted in a
broken shape a good repairer should recover.
`json_in_content`, `toolName_brace_json`, `xml_tool_code`,
`partial_openai_fields`, `markdown_fenced_json`, `json_with_prose`,
`python_call_syntax`, `provider_specific`.

**No-tool natural language** (gold = `no_tool`): the model answered or asked a
question and made no call; repairing it would fabricate one.
`prose_false_positive`, `plain_answer`, `clarifying_question`,
`literal_commands`, `code_snippet_mention`, `documentation_example`,
`structured_data_no_intent`.

**Unsafe / ambiguous** (gold = `no_tool`): a concrete call cannot be recovered
without guessing, or the text is adversarial, so conservative non-repair is
correct. `missing_required_args`, `ambiguous_tool_choice`, `truncated_tool_call`,
`unsafe_guessed_intent`, `injection_force_tool`, `unknown_tool_near_match`.

A fabricated call on the unsafe family (`UNSAFE_TAXONOMY` in
[`tcrb/scorer.py`](tcrb/scorer.py)) counts as an **unsafe false positive**: the
repaired call would act on invented or coerced intent. `unknown_tool_near_match`
is scored as an ordinary fabrication (a precision hit) rather than an unsafe FP,
because snapping to the nearest offered name is a wrong-target error, not an
execution of guessed intent.

## Labeling policy

A gold label must be **defensible from `raw_output` alone**. The labeler does
not import outside knowledge of what the model "meant". If the intended call is
not recoverable from the emitted string plus the offered `request_tools`, it is
not a valid gold `tool_call` and the gold is `no_tool`. When mapping the raw
output to gold requires a judgment call, the reasoning is recorded in `note` —
a documented ambiguity, never a license to guess.

`no_tool` cases are first-class. The corpus splits them across the no-tool and
unsafe/ambiguous taxonomies precisely so the per-taxonomy table shows *where* a
repairer fabricates.

## Provenance: captured vs synthetic

Every case records explicit provenance. The authoritative flag is
`provenance.kind`:

- **`captured`** — `raw_output` was captured verbatim (or as a clearly noted
  excerpt) from a live local-model run. Captured cases name a real `model` and,
  when known, the `runtime` (e.g. `ollama`), `harness` (e.g. `opencode`),
  `prompt_id`, and `temperature`.
- **`synthetic`** — `raw_output` was hand-authored to model a known failure
  shape. Synthetic cases set `model` to `"synthetic"` and are useful for
  exercising repair behavior, but are **not** evidence of real-world
  frequencies.

`make validate` enforces that `kind` is present and self-consistent: the legacy
`synthetic` boolean must agree with `kind`, captured cases must not be labeled
`synthetic`, and synthetic cases must set `model` to `"synthetic"`. See
[`tcrb/schema_validate.py`](tcrb/schema_validate.py).

The corpus is honest about its composition. It now includes a larger reviewed
captured subset from the 2026-06-14 local Ollama panel, while preserving raw
captures separately. Do not read raw capture frequencies as benchmark weights:
only promoted, reviewed files in `corpus/cases/` are scored, and synthetic cases
remain worked examples that pin the schema and scoring. Pending scaffolds under
`corpus/pending/` are local ignored review scratch for the first public release;
they are not part of `make leaderboard`.

## Scoring policy and why false positives matter more than misses

A missed repair (false negative) degrades to the status quo: the client did not
understand the call, which is exactly what happens without any repairer. A
fabricated repair (false positive) is strictly worse: it manufactures an action
the model never committed to. On the unsafe family that action runs on guessed
or adversarially-coerced intent — deleting a file, running a command, writing to
an invented path.

Therefore the leaderboard ranks **precision-first**, in this order:

1. fewest unsafe false positives,
2. highest precision,
3. highest recoverable recall,
4. highest F1 (last tiebreak).

This is why `greedy_name_match` — which wins recall and F1 by emitting a call
whenever a tool name appears — sorts to the bottom: it racks up unsafe false
positives. A conservative repairer may have lower recoverable recall and still
be preferable if it avoids fabricating actions. In particular,
`local_tool_proxy` is scoped to structured/recoverable shapes; it is not meant to
infer broad prose intent. The ordering and the metrics are computed
deterministically in [`tcrb/leaderboard.py`](tcrb/leaderboard.py).

## How to add a new case

1. Create `corpus/cases/NNNN-short-slug.json` (the `id` must equal the filename
   stem). Pretty-print with 2-space indent and a trailing newline.
2. Fill in `provenance` with an explicit `kind`. For captured cases, record the
   model, runtime, harness, and date; sanitize secrets, credentials, local
   paths, and private code first (see [`SECURITY.md`](SECURITY.md)). For
   synthetic cases, set `model` to `"synthetic"` and describe the shape in
   `source`.
3. Put the exact emitted string in `raw_output` (byte-for-byte; for a captured
   excerpt, say so in `note`).
4. Tag the `taxonomy` and write the `gold` label, defensible from `raw_output`
   alone. Add a `note` for any judgment call.
5. Run `make validate` (schema + cross-case integrity) and `make test`.
6. Regenerate the leaderboard with `make leaderboard` and review the diff.

A non-network capture helper is available to scaffold *pending* captured cases
for human review — see [Capture workflow](#capture-workflow-optional).

## Reproducing the leaderboard

```bash
python3 -m pip install -e ".[dev]"
make validate     # schema + corpus integrity
make test         # unit tests
make leaderboard  # regenerate README table + corpus/results.json
```

The output is deterministic given a fixed corpus and adapter set: adapters and
cases are iterated in sorted order with no clock or randomness, so running
`make leaderboard` twice produces no diff. The pure-Python rows (`naive_json`,
`greedy_name_match`) reproduce exactly from any checkout. The `local_tool_proxy`
adapter requires the sibling library (`pip install -e ../local-tool-proxy`);
without it that row reports `unavailable` and every other adapter still scores.
The checked-in `local_tool_proxy` numbers were generated with
`local-tool-proxy` 0.1.0 — pin that version to reproduce that row. See the
top-level [`README.md`](README.md) for the side-by-side clone instructions.

## Captured model panel: 2026-06-14

The first larger local-model panel is documented in
[`docs/captured-model-panel-2026-06-14.md`](docs/captured-model-panel-2026-06-14.md):

- 6 local Ollama models, 20 prompts per model.
- Deterministic capture settings: `temperature=0`, `num_predict=384`.
- 120/120 successful raw captures stored under `captures/raw/2026-06-14/`.
- 80 reviewed cases promoted into `corpus/cases/`; numeric ID gaps are expected
  because this is a curated subset, not a one-to-one promotion of every capture.
- 43 pending scaffolds remain local/ignored under `corpus/pending/` for now;
  they are unscored and not part of the public corpus.

The capture-time output classes in that document are triage heuristics, not the
closed schema taxonomy. Promoted cases are labeled from the emitted raw text with
a schema taxonomy and a gold `tool_call` or `no_tool` label.

## Capture workflow (optional)

`tcrb/capture.py` (also `make capture-ollama`) scaffolds captured cases without
making any network call by default. It reads a raw model-output file plus
metadata flags and emits a **pending** case JSON under `corpus/pending/` with
`gold` left unset and `taxonomy` empty, for a human to label and promote. It
never auto-labels, never requires API keys, and never contacts a model unless
explicitly pointed at a local endpoint. See `python3 -m tcrb.capture --help`.

## Limitations of the current corpus

- It is still small and **not definitive**. The 2026-06-14 panel materially
  improves captured coverage, but scores still characterize this corpus only.
- Captured coverage is local-model/Ollama-heavy and based on one fixed
  20-prompt panel. It does not measure end-to-end agent success or production
  tool execution.
- Synthetic cases encode plausible shapes, not measured frequencies. Do not read
  per-taxonomy counts as "how often models do this".
- Raw capture counts and promoted benchmark counts are deliberately separate:
  raw captures prove provenance; reviewed `corpus/cases/` files define the
  scored benchmark.
