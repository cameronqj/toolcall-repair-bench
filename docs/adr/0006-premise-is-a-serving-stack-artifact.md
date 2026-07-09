# ADR 0006: The Premise Is A Serving-Stack Artifact (Archival)

## Status

Accepted — and archival. This ADR records the finding that led the project to be
frozen read-only. See the top-level `README.md` and [`findings/`](../../findings/).

## Context

The benchmark was built on the premise that small local models frequently emit tool
calls in malformed, unparseable shapes, and that a repair layer is therefore useful.
The corpus was assembled from raw outputs captured on the 2026-06-14 local model panel.

Follow-up testing established that the captures were taken via Ollama's `/api/generate`
endpoint — the raw text-completion path, which accepts no `tools` parameter and runs no
tool-call parser. It records the model's native tool syntax as plain text, before any
parser runs. That is the source of every malformed shape in the corpus.

On the endpoints real clients use — `/v1/chat/completions` (Ollama) and llama.cpp with
`--jinja` — the server applies the model's chat template and parses the call before the
client sees it. The same models that produce "malformed" text on `/api/generate` return
clean OpenAI `tool_calls` on those endpoints. This was verified across both stacks,
streaming and non-streaming, including parallel multi-tool calls and the original
`gemma4:e4b-mlx` seed model, with tool-call arguments reassembled from fragmented SSE
deltas so the streaming assembly path was genuinely exercised. Full evidence and
reproduction scripts are under `findings/`.

## Decision

Freeze the repository read-only rather than delete it. Reframe the top-level `README.md`
to lead with the finding, scope every corpus claim to the `/api/generate` (unparsed)
regime, and add `findings/` with the reproduction scripts and recorded results.

The premise is corrected, not the methodology: the precision-first scoring, the
first-class `no_tool` treatment, the fabrication penalties, and the captured-vs-synthetic
provenance discipline all stand and remain reusable. What is retracted is the *framing* —
"small local models emit malformed tool calls" — which is more precisely "raw model text
needs parsing, and most serving stacks now do that for you on the chat endpoint."

## Consequences

The repair layer this benchmark evaluates is a no-op on every stack tested. The repair
niche is real but narrow: consumers of raw completions (`/api/generate`, raw llama.cpp
without `--jinja`, or custom loops that parse model text themselves). The benchmark
should not be cited as a measure of model or library quality. It stands as an honest
record of an eval catching that its own premise was too broad — which is the mechanism
the project was built to provide.
