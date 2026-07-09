# toolcall-repair-bench corpus

A frozen, hermetic set of raw local-model outputs labeled with auditable gold tool calls. Each case is a single string paired with the tools that were offered in the request and one defensible gold label: either a specific tool call or `no_tool`. The corpus exists to measure whether a "repair" layer can recover the intended tool call from malformed model output without fabricating calls that were never made — and whether it knows when to abstain.

## Status

**This is an initial corpus of 117 cases, not yet a definitive benchmark.** It is large enough to show the precision/recall frontier and exercise every taxonomy category, but far too small to make general claims about any model or library. Do not cite it as a definitive benchmark result, a model score, or a repair-rate.

The 117 cases are a mix, clearly labeled in provenance (`provenance.kind`):

- **85 real captured cases** — a few seed fixtures originally collected for `local-tool-proxy` (including `0029`, a verbatim excerpt of a `gemma4:e4b-mlx` run where the model printed shell commands as numbered prose instead of calling tools) plus a reviewed subset of the 2026-06-14 local Ollama panel (6 models × 20 prompts; see [`../docs/captured-model-panel-2026-06-14.md`](../docs/captured-model-panel-2026-06-14.md)). Captured `raw_output` is preserved verbatim, with raw provenance under `captures/raw/`.
- **32 synthetic cases** — hand-authored to model failure shapes commonly seen from small local models, each with `provenance.kind: "synthetic"`. This includes a batch of **negative controls** (`0030`–`0037`): ordinary JSON in an answer, a code snippet naming a tool, a documentation example, a near-miss unknown tool name, prompt-injection text, structured data, and floated-but-unchosen tools — all gold `no_tool`. They are realistic and useful for exercising repair behavior, but they are illustrative, not measurements of how often any real model emits them.

The corpus is now **majority-captured** (85 captured / 32 synthetic). It was previously tiny because the upstream proxy's tracing was deliberately sanitized (it persisted collapse *metadata*, not raw model-output text), so very few verbatim malformed strings existed to add without fabricating; the 2026-06-14 panel added verbatim captured strings. Roadmap target: broader, deduped, multi-model **captured** coverage spanning every taxonomy category. Synthetic cases remain worked examples that pin the schema and the scoring behavior, not evidence about real-world frequencies. Captured coverage is still local-Ollama-only and **concentrated by base-model family**: the two `carnice:9b-q4km` tags contribute 37 of the 85 captured cases, and since Carnice-9b is a Qwen3.5-9B derivative (see the [panel notes](../docs/captured-model-panel-2026-06-14.md)), those plus `qwen35:9b-q4km-chat` (20 cases) are about two-thirds of the captured set. Per-model and per-taxonomy counts are illustrative coverage, not representative weights.

## Outcome classes

Every case falls into one of three classes. Distinguishing them is the entire point of the corpus:

1. **Recoverable malformed intent** — gold is a `tool_call`. The model clearly meant to make one specific call but emitted it in a broken shape; a good repairer recovers it. Taxonomy tags: `json_in_content`, `toolName_brace_json`, `xml_tool_code`, `partial_openai_fields`, `markdown_fenced_json`, `json_with_prose`, `python_call_syntax`, `provider_specific`.
2. **No-tool natural language** — gold is `no_tool`. The model answered or asked a question and made no call; repairing it would fabricate one. Taxonomy tags: `prose_false_positive`, `plain_answer`, `clarifying_question`.
3. **Unsafe / ambiguous** — gold is `no_tool`. A concrete call cannot be recovered without guessing, so conservative non-repair is correct. Taxonomy tags: `missing_required_args`, `ambiguous_tool_choice`, `truncated_tool_call`, `unsafe_guessed_intent`.

Classes 2 and 3 both have gold `no_tool`: any emitted call is a false positive. They are split in the taxonomy so the per-taxonomy table shows *where* a repairer fabricates.

## Case Schema

Source of truth: [`schema/case.schema.json`](schema/case.schema.json) (JSON Schema draft 2020-12). One JSON file per case under `cases/`, pretty-printed with 2-space indent and a trailing newline. Additional properties are rejected at the top level, inside `provenance`, and inside each `gold` variant, so the schema is strict and auditable.

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `id` | string | yes | Kebab-case slug, e.g. `0001-json-in-content`. |
| `provenance` | object | yes | Attribution for the raw output. See [Provenance Fields](#provenance-fields). |
| `request_tools` | array | yes | The tools offered in the request (OpenAI-style function tools minus the outer wrapper). Each item is `{ "name": string (required), "description"?: string, "parameters"?: object }`. The scorer derives the valid tool NAMES from this array. |
| `raw_output` | string | yes | The exact string the model emitted, reproduced byte-for-byte including trailing newlines. |
| `taxonomy` | array of strings | yes (minItems 1) | One or more labels from the closed enum. See [Taxonomy](#taxonomy). |
| `gold` | object | yes | The auditable gold label. Either `{ "type": "tool_call", "name": string, "arguments": object }` or `{ "type": "no_tool" }`. See [Gold Labels](#gold-labels). |
| `note` | string | no | Explanation for an ambiguous gold label. A note, not a guess. |

## Taxonomy

The taxonomy describes the **SHAPE** of the output, not why the model produced it. The enum is closed; a case may carry more than one label. Tags are grouped here by the [outcome class](#outcome-classes) they belong to.

**Recoverable shapes (gold = `tool_call`):**

- **`json_in_content`** — a complete tool call emitted as JSON in the content channel instead of the structured `tool_calls` field. Example: `{"name": "write_file", "arguments": {"path": "buggy.py", "content": "..."}}` printed as text.
- **`toolName_brace_json`** — the tool name followed immediately by a JSON-ish brace blob, often invalid JSON (single quotes, trailing commas, unquoted keys). Example: `run_terminal_cmd{'command': 'pytest -q',}`.
- **`xml_tool_code`** — an XML-ish wrapper around a call. Example: `<tool_code>run_command("mkdir x")</tool_code>` or `<tool_call>{...}</tool_call>`.
- **`partial_openai_fields`** — an OpenAI-shaped call with missing or mis-keyed fields, e.g. `arguments` carried as a JSON string and the outer `type` absent.
- **`markdown_fenced_json`** — the call wrapped in a Markdown code fence, e.g. a ```` ```json ```` or ```` ```tool_code ```` block.
- **`json_with_prose`** — a valid call embedded in explanatory prose before and/or after it.
- **`python_call_syntax`** — a Python-style call, e.g. `get_stock_price(symbol="AAPL", period="1d")`.
- **`provider_specific`** — a provider-specific wrapper, e.g. a Llama-style `<|python_tag|>{...}` or Mistral-style `[TOOL_CALLS][...]`.

**No-tool natural language (gold = `no_tool`):**

- **`prose_false_positive`** — prose that mentions a tool name but makes NO call. Example: "I will `write_file` after I inspect the project." First-class cases: they penalize repairers that fabricate by grepping for tool names.
- **`plain_answer`** — an ordinary natural-language answer; a tool was offered but none was needed.
- **`clarifying_question`** — the model asks the user for missing information instead of calling.
- **`literal_commands`** — the model printed the commands it would run as text (e.g. numbered shell/git steps) instead of calling a tool. Real captured failure mode of small models under rigid prompts.
- **`code_snippet_mention`** — an illustrative code snippet that defines or calls a function sharing a tool's name; not an invocation.
- **`documentation_example`** — text that *shows how* a tool could be called, often with placeholder arguments; a how-to, not a call.
- **`structured_data_no_intent`** — a natural-language answer that includes structured data (a JSON blob, a table) which is the answer itself, not tool arguments.

**Unsafe / ambiguous (gold = `no_tool`):**

- **`missing_required_args`** — the output names a tool but omits (or leaves empty) a required argument; repairing would invent it.
- **`ambiguous_tool_choice`** — two or more offered tools fit and the output does not commit; picking one is a guess.
- **`truncated_tool_call`** — the output is cut off mid-call (unterminated JSON); completing it is a guess.
- **`unsafe_guessed_intent`** — only a vague gesture at acting, with no concrete call to recover.
- **`injection_force_tool`** — adversarial / prompt-injection text that orders the repair layer to force a tool call. A repairer must not be coerced into fabricating one.
- **`unknown_tool_near_match`** — a well-formed call to a tool name that was *not* offered, but is close to one that was. Snapping it to the nearest offered name is a guess.

A fabrication on the unsafe/ambiguous family (`injection_force_tool`, `missing_required_args`, `ambiguous_tool_choice`, `truncated_tool_call`, `unsafe_guessed_intent`) is an **unsafe false positive** — the worst failure the scorer tracks, surfaced in the leaderboard's `Unsafe FP` column. `unknown_tool_near_match` is scored as an ordinary fabrication (a precision hit), not an unsafe FP.

### Relationship to local-tool-proxy "collapse" categories

The sibling `local-tool-proxy` repo has a related but distinct axis: "collapse" categories such as `tool_intent_prose` and `literal_commands` describe **WHY** a model stopped using tools, not the **SHAPE** of a malformed payload. The two axes are orthogonal. The one direct correspondence: this corpus's `prose_false_positive` lines up with the proxy's `tool_intent_prose`.

## Provenance Fields

Provenance is **required** — a case cannot be added without it, so every raw output is traceable.

- **`kind`** (required) — `captured` or `synthetic`. The single authoritative provenance flag. `make validate` enforces it and checks cross-field consistency: a captured case must name a real model (not `synthetic`); a synthetic case must set `model` to `synthetic`; and the legacy `synthetic` boolean, if present, must agree with `kind`.
- **`model`** (required) — the local model that produced the output, e.g. `gemma4:e4b-mlx`, or `synthetic` for hand-authored cases.
- **`runtime`** — the inference runtime for a captured case, e.g. `ollama`, `mlx`, `llama.cpp`, or `unknown`. Omit (or `n/a`) for synthetic.
- **`harness`** — the client/harness that issued the request for a captured case, e.g. `opencode`, `openai-compatible`, `codex-cli`, or `unknown`. Omit (or `n/a`) for synthetic.
- **`prompt_id`** — stable identifier for the prompt/task that elicited the output, if known.
- **`temperature`** — decoding temperature for a captured case if known, else `unknown`.
- **`sampler`** — decoding / sampler settings if known, otherwise `unknown` (or `n/a` for synthetic cases).
- **`captured`** — ISO date the output was captured or authored.
- **`source`** (required) — where the raw output came from: a repo, a fixture path, a capture session, or a description of the hand-authored shape. Specific enough that another person could find or understand the original.
- **`synthetic`** — legacy boolean mirror of `kind` (true iff `kind == "synthetic"`). Retained for backward compatibility; `kind` is authoritative.

## Gold Labels

A gold label must be **defensible from `raw_output` alone**. The labeler does not get to import outside knowledge of what the model "meant"; if the intended call is not recoverable from the emitted string and the offered `request_tools`, it is not a valid gold tool call.

Two shapes only:

- `{ "type": "tool_call", "name": <one of request_tools names>, "arguments": { ... } }`
- `{ "type": "no_tool" }`

When mapping the raw output to gold requires a judgment call — e.g. binding a positional argument to a named parameter — record the reasoning in `note`. The note documents an ambiguity; it does not license a guess.

## License

The corpus (this directory: schema, cases, and documentation) is licensed **CC BY 4.0** — see [`LICENSE`](LICENSE). Code elsewhere in the repository is licensed MIT separately.
