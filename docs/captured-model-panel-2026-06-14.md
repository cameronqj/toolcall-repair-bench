# Captured model panel — 2026-06-14

Sequential Ollama `/api/generate` capture on the RTX 3070 VM. The panel preserves raw model output separately from the labeled benchmark corpus.

Configuration:
- Runtime: Ollama local API (`ollama-api-generate`)
- Sampling: `temperature=0`, `num_predict=384`
- Prompt set: 20 fixed tool-intent / no-tool / unsafe prompts per model

Public corpus summary:

| item | count |
| --- | ---: |
| models | 6 |
| prompts/model | 20 |
| raw captures | 120 |
| successful captures | 120 |
| promoted reviewed cases from this panel | 80 |
| total scored cases after promotion | 117 |
| captured scored cases | 85 |
| synthetic scored cases | 32 |
| pending/unreviewed scaffolds | 43 local files, ignored/not committed |

Paths:
- Raw captures: `captures/raw/2026-06-14/`
- Panel summary JSON: `captures/raw/2026-06-14/panel/summary.json`
- Promoted curated subset: `corpus/cases/`
- Pending scaffolds policy: do **not** commit for the first public release. They are local review scratch under ignored `corpus/pending/`; only `corpus/cases/` is authoritative for scoring.

Important: the capture-time output class is a heuristic used for panel triage. Promoted benchmark cases use the schema taxonomy and gold label after review of the raw emitted text. Capture counts are not benchmark weights.

| model | captures | success | semi_structured | structured | no_tool | missing_args | prose_intent | unrecoverable | repairable_share | unsafe_abstain_share | promoted |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| carnice:9b-q4km | 20 | 20 | 9 | 4 | 5 | 1 | 0 | 1 | 65% | 35% | 17 |
| carnice:9b-q4km-code-nothink | 20 | 20 | 0 | 0 | 13 | 5 | 2 | 0 | 0% | 100% | 20 |
| gemma4:12b-it-qat | 20 | 20 | 2 | 1 | 4 | 0 | 0 | 13 | 15% | 85% | 9 |
| gemma4:e2b-code | 20 | 20 | 15 | 0 | 5 | 0 | 0 | 0 | 75% | 25% | 10 |
| gemma4:e4b-it-qat | 20 | 20 | 8 | 6 | 5 | 1 | 0 | 0 | 70% | 30% | 4 |
| qwen35:9b-q4km-chat | 20 | 20 | 12 | 6 | 2 | 0 | 0 | 0 | 90% | 10% | 20 |

Model notes:

- **`carnice:9b-q4km`** (and its `carnice:9b-q4km-code-nothink` variant) is the local Ollama alias for Carnice-9b Q4_K_M GGUF (`kai-os/Carnice-9b-GGUF` on Hugging Face), a GGUF export of `kai-os/Carnice-9b` — built from `Qwen/Qwen3.5-9B` and tuned for the Hermes-Agent harness. The `-code-nothink` tag is the same model run with a code-oriented template that suppresses `<think>` blocks (which is why its captures are mostly leaked reasoning rather than a committed call).
- Because Carnice-9b is a **Qwen3.5-9B derivative**, the captured set leans heavily on one base-model family: the two `carnice` tags (37 cases) plus `qwen35:9b-q4km-chat` (20 cases) together are ~67% of the 85 captured cases. Treat per-model and per-taxonomy counts as illustrative coverage, not a representative model sample.

Aggregate capture classes:

| capture output class | captured | promoted |
| --- | ---: | ---: |
| `semi_structured_repairable` | 46 | 32 |
| `structured_repairable` | 17 | 12 |
| `no_tool` | 34 | 17 |
| `missing_required_args` | 7 | 7 |
| `prose_intent` | 2 | 2 |
| `unrecoverable_malformed` | 14 | 10 |

Promotion policy:
- Promote a representative subset first, not every captured row.
- Keep rare classes represented: both `prose_intent`, all 7 `missing_required_args` heuristic rows, and 10 empty/unrecoverable rows were included.
- Include every model in the promoted subset; Gemma E2B contributes provider-specific / partial-format cases that class-first selection would otherwise miss.
- Avoid duplicate Qwen representations; canonical slug is `qwen35-9b-q4km-chat`.
- Preserve all raw captures for provenance, but score only reviewed cases in `corpus/cases/`.
