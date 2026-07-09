#!/usr/bin/env python3
"""Capture tool-call SHAPE across models on an OpenAI-compatible endpoint (non-streaming).

Question: does a parsing serving stack (llama.cpp `--jinja`, or Ollama's
`/v1/chat/completions`) emit clean OpenAI `tool_calls`, or the malformed-in-content
shapes this corpus targets (which were captured from Ollama's raw `/api/generate`
endpoint)? Hits each model with tool-requiring prompts and classifies:
clean_tool_calls vs malformed:<shape> vs plain_prose (declined).

Config (no host details are baked in):
  TCRB_ENDPOINT  OpenAI-compatible chat-completions URL
                 (default http://localhost:8080/v1/chat/completions)
  TCRB_MODELS    comma-separated model ids as your server names them
"""
import json
import os
import re
import urllib.request

BASE = os.environ.get("TCRB_ENDPOINT", "http://localhost:8080/v1/chat/completions")
MODELS = [m.strip() for m in os.environ.get(
    "TCRB_MODELS", "gemma4:e4b,gemma4:12b,qwen3.5:9b,gpt-oss:20b").split(",") if m.strip()]

WEATHER = {"type": "function", "function": {"name": "get_weather",
           "description": "Get the current weather for a city",
           "parameters": {"type": "object", "properties": {"city": {"type": "string"}},
                          "required": ["city"]}}}
SEARCH = {"type": "function", "function": {"name": "web_search",
          "description": "Search the web for recent information",
          "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                         "required": ["query"]}}}
EVENT = {"type": "function", "function": {"name": "create_event",
         "description": "Create a calendar event",
         "parameters": {"type": "object", "properties": {
             "title": {"type": "string"}, "date": {"type": "string"},
             "attendees": {"type": "array", "items": {"type": "string"}}},
             "required": ["title", "date"]}}}

PROMPTS = [
    ("weather", "Check the current weather in Tokyo. You must call the get_weather tool now.", [WEATHER]),
    ("search", "Who won the 2026 UEFA Champions League final? This is recent -- you must use the web_search tool.", [SEARCH]),
    ("event", "Schedule a meeting titled 'Q3 review' on 2026-07-15 with alice and bob. Use the create_event tool.", [EVENT]),
]

# repair-bench-style shape taxonomy for content that ISN'T parsed into tool_calls
SHAPE_PATS = [
    ("markdown_fenced_json", r"```(?:json|tool_code|tool_call)"),
    ("xml_tool_code", r"<(?:tool_call|function|tool|invoke|parameter)\b"),
    ("python_call_syntax", r"\b[a-z_]\w*\s*\([^)]*=[^)]*\)"),
    ("toolName_brace_json", r"\b[a-z_]\w*\s*\{\s*\""),
    ("json_in_content", r"\{[^{}]*\"(?:name|arguments|function|parameters|tool|query|city|title)\""),
]


def _valid_args(c):
    try:
        json.loads(c.get("function", {}).get("arguments") or "{}")
        return True
    except Exception:
        return False


def classify_content(content):
    c = content or ""
    if not c.strip():
        return "empty_content"
    hits = [name for name, p in SHAPE_PATS if re.search(p, c, re.I | re.S)]
    return "malformed:" + ",".join(hits) if hits else "plain_prose"


def call(model, prompt, tools, timeout):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "tools": tools, "tool_choice": "auto", "temperature": 0,
                       "max_tokens": 256, "stream": False}).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


results = []
for model in MODELS:
    print(f"=== {model} ===", flush=True)
    for i, (name, prompt, tools) in enumerate(PROMPTS):
        timeout = 300 if i == 0 else 120  # first call to a model triggers a load/swap
        try:
            d = call(model, prompt, tools, timeout)
            ch = (d.get("choices") or [{}])[0]
            m = ch.get("message", {}) or {}
            tc = m.get("tool_calls")
            if tc:
                ok = all(_valid_args(c) for c in tc)
                verdict = "clean_tool_calls" if ok else "tool_calls_bad_args"
                detail = [(c.get("function", {}).get("name"), c.get("function", {}).get("arguments")) for c in tc]
            else:
                verdict = classify_content(m.get("content"))
                detail = (m.get("content") or "")[:240]
            print(f"  {name:<8} finish={ch.get('finish_reason'):<12} -> {verdict}", flush=True)
            results.append({"model": model, "prompt": name, "verdict": verdict,
                            "finish_reason": ch.get("finish_reason"), "detail": detail})
        except Exception as e:
            print(f"  {name:<8} ERROR {type(e).__name__}: {e}", flush=True)
            results.append({"model": model, "prompt": name, "verdict": "error", "detail": str(e)[:200]})

os.makedirs("results", exist_ok=True)
json.dump(results, open("results/toolshape.json", "w"), indent=2)

print("\n=== SUMMARY (verdict per prompt: weather / search / event) ===", flush=True)
by_model = {}
for r in results:
    by_model.setdefault(r["model"], {})[r["prompt"]] = r["verdict"]
clean_models = 0
for m in MODELS:
    v = by_model.get(m, {})
    row = [v.get("weather", "-"), v.get("search", "-"), v.get("event", "-")]
    allclean = all(x == "clean_tool_calls" for x in row)
    clean_models += allclean
    print(f"  {m:<20} {'  '.join(x[:18] for x in row)}{'   [ALL CLEAN]' if allclean else ''}", flush=True)
print(f"\n{clean_models}/{len(MODELS)} models emit clean OpenAI tool_calls on all 3 prompts.", flush=True)
print("Saved results/toolshape.json", flush=True)
