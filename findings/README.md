# Findings: the malformed shapes are a serving-stack artifact

This directory holds the evidence behind the archival note in the top-level
[`README.md`](../README.md): the "malformed tool call" outputs this benchmark was
built to repair are **largely an artifact of the capture endpoint**, not a behavior
of the models.

## The mechanism

The corpus was captured via Ollama's **`/api/generate`** — the raw text-completion
endpoint. It takes **no `tools` parameter and runs no tool-call parser**, so it
records the model's native tool syntax *as plain text*, before any parser touches it.
That is the origin of every "malformed" shape in the taxonomy (`json_in_content`,
`xml_tool_code`, `toolName{...}`, and the rest).

The paths a real client (OpenCode, Aider, any OpenAI SDK) actually uses —
`/v1/chat/completions` on Ollama, or llama.cpp with `--jinja` — apply the model's
chat template and parse the call **before the client ever sees it**.

### Same model, same prompt, endpoint is the only variable

Model `gemma4:e4b-mlx` (the model that produced the original seed captures), identical
prompt:

| Endpoint | Output |
| --- | --- |
| `/api/generate` (no parser) | `{"name":"get_weather","arguments":{"city":"Seattle","units":"imperial"}}` returned as raw text, with **no `tool_calls` field** — this is the corpus's `json_in_content` shape |
| `/v1/chat/completions` (parser runs) | `finish_reason: tool_calls`, parsed cleanly, empty `content` |

## The panels

| Stack / path | Models | Result |
| --- | --- | --- |
| llama.cpp `--jinja`, non-streaming | 9 (Gemma-4 + Qwen families) | 27/27 clean |
| llama.cpp `--jinja`, streaming + parallel | 9 (Gemma-4 + Qwen families) | 36/36 clean |
| Ollama `/v1/chat/completions`, streaming + parallel | 4 (incl. `gemma4:e4b-mlx` seed model) | 16/16 clean |

Every call returned `finish_reason: tool_calls` with valid JSON arguments; nothing
leaked into `content`. For the streaming panels, tool-call arguments were reassembled
from **fragmented SSE deltas**, so the streaming assembly path — the one most likely
to leak a partial shape — was genuinely exercised.

The verbatim per-call output for the Ollama streaming panel is in
[`results/ollama_chat_streaming.json`](results/ollama_chat_streaming.json) (all public
model tags). The llama.cpp panels ran against a set of local Gemma-4/Qwen models served
under host-specific aliases; those raw logs are omitted to avoid publishing a private
roster — re-run the scripts against your own endpoint to reproduce them.

## Reproduce it

The scripts are dependency-free (Python 3 stdlib only). No host details are baked in;
point them at your own endpoint:

```bash
# A parsing chat endpoint: llama.cpp --jinja on :8080, or Ollama on :11434.
export TCRB_ENDPOINT="http://localhost:8080/v1/chat/completions"
export TCRB_MODELS="model-a,model-b,model-c"   # as your server names them

python3 findings/toolshape_capture.py          # non-streaming shape panel
python3 findings/toolshape_stream_capture.py    # streaming + parallel, reassembled from SSE deltas

# The tightest reproduction: Ollama chat endpoint, streaming, incl. the seed model.
export TCRB_ENDPOINT="http://localhost:11434/v1/chat/completions"
export TCRB_MODELS="gemma4:e4b-mlx,qwen3.5:9b,gpt-oss:20b"
python3 findings/toolshape_stream_ollama.py
```

To reproduce the raw-vs-parsed contrast for a single model, send the same prompt to
Ollama's `/api/generate` (no `tools`, no parser) and to `/v1/chat/completions` (with
`tools`): the former returns the tool call as text in `response`, the latter as a
parsed `tool_calls` entry.

## What it means

The repair layer this benchmark evaluates is a **no-op** on every stack tested here.
The repair niche is real but narrow: consumers of *raw* completions — `/api/generate`,
raw llama.cpp without `--jinja`, or custom agent loops that parse model text
themselves. "Small local models emit malformed tool calls" is more precisely: *raw
model text needs parsing, and most serving stacks now do that for you on the chat
endpoint.*
