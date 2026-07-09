#!/usr/bin/env python3
"""Ollama chat-endpoint STREAMING tool-shape capture (the tightest reproduction).

Closes the residual gap for this benchmark's premise. The corpus's malformed
shapes were captured via Ollama /api/generate (raw completion, no tool parser).
This hits Ollama's OpenAI-compatible /v1/chat/completions with tools AND
stream:true, reassembling tool_calls from SSE deltas like an agent client would
-- on the SAME model family, including gemma4:e4b-mlx (the original seed-capture
model). Same weights, parsing endpoint, streaming: does it still leak?

Config (no host details are baked in):
  TCRB_ENDPOINT  OpenAI-compatible chat-completions URL
                 (default http://localhost:11434/v1/chat/completions -- Ollama)
  TCRB_MODELS    comma-separated Ollama model tags present on your host
"""
import json
import os
import re
import urllib.request

BASE = os.environ.get("TCRB_ENDPOINT", "http://localhost:11434/v1/chat/completions")
MODELS = [m.strip() for m in os.environ.get(
    "TCRB_MODELS", "gemma4:e4b-mlx,gemma4:12b-it-qat,qwen3.5:9b,gpt-oss:20b").split(",") if m.strip()]

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
    ("parallel", "Do two things now: (1) check the weather in Paris with get_weather, and (2) search the web for the 2026 Wimbledon champion with web_search. Call both tools.", [WEATHER, SEARCH]),
]

SHAPE_PATS = [
    ("markdown_fenced_json", r"```(?:json|tool_code|tool_call)"),
    ("xml_tool_code", r"<(?:tool_call|function|tool|invoke|parameter)\b"),
    ("python_call_syntax", r"\b[a-z_]\w*\s*\([^)]*=[^)]*\)"),
    ("toolName_brace_json", r"\b[a-z_]\w*\s*\{\s*\""),
    ("json_in_content", r"\{[^{}]*\"(?:name|arguments|function|parameters|tool|query|city|title)\""),
]


def classify_content(content):
    c = content or ""
    if not c.strip():
        return "empty_content"
    hits = [name for name, p in SHAPE_PATS if re.search(p, c, re.I | re.S)]
    return "malformed:" + ",".join(hits) if hits else "plain_prose"


def stream_call(model, prompt, tools, timeout):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "tools": tools, "tool_choice": "auto", "temperature": 0,
                       "max_tokens": 256, "stream": True}).encode()
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"})
    content_parts, tcs, arg_frag_counts = [], {}, {}
    finish_reason, n_chunks = None, 0
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except Exception:
                continue
            n_chunks += 1
            ch = (chunk.get("choices") or [{}])[0]
            if ch.get("finish_reason"):
                finish_reason = ch["finish_reason"]
            delta = ch.get("delta") or {}
            if delta.get("content"):
                content_parts.append(delta["content"])
            for tcd in (delta.get("tool_calls") or []):
                idx = tcd.get("index", 0)
                slot = tcs.setdefault(idx, {"name": None, "args": [], "id": None})
                if tcd.get("id"):
                    slot["id"] = tcd["id"]
                fn = tcd.get("function") or {}
                if fn.get("name"):
                    slot["name"] = fn["name"]
                if fn.get("arguments") is not None:
                    slot["args"].append(fn["arguments"])
                    arg_frag_counts[idx] = arg_frag_counts.get(idx, 0) + 1
    reassembled, all_args_valid = [], True
    for idx in sorted(tcs):
        slot = tcs[idx]
        args_str = "".join(slot["args"])
        try:
            parsed, valid = json.loads(args_str or "{}"), True
        except Exception:
            parsed, valid, all_args_valid = None, False, False
        reassembled.append({"name": slot["name"], "args_str": args_str,
                            "args_parsed": parsed, "valid": valid})
    return {"reassembled": reassembled, "content": "".join(content_parts),
            "finish_reason": finish_reason, "n_chunks": n_chunks,
            "arg_frag_counts": arg_frag_counts, "all_args_valid": all_args_valid}


results = []
for model in MODELS:
    print(f"=== {model} ===", flush=True)
    for i, (name, prompt, tools) in enumerate(PROMPTS):
        timeout = 300 if i == 0 else 180
        try:
            d = stream_call(model, prompt, tools, timeout)
            if d["reassembled"]:
                verdict = "clean_tool_calls" if d["all_args_valid"] else "tool_calls_bad_args"
                detail = [(t["name"], t["args_str"]) for t in d["reassembled"]]
            else:
                verdict = classify_content(d["content"])
                detail = d["content"][:240]
            fragged = any(c > 1 for c in d["arg_frag_counts"].values())
            print(f"  {name:<9} finish={str(d['finish_reason']):<12} chunks={d['n_chunks']:<4} "
                  f"frag={'Y' if fragged else 'n'} -> {verdict}", flush=True)
            results.append({"model": model, "prompt": name, "verdict": verdict,
                            "finish_reason": d["finish_reason"], "n_chunks": d["n_chunks"],
                            "arg_fragmented": fragged, "detail": detail})
        except Exception as e:
            print(f"  {name:<9} ERROR {type(e).__name__}: {e}", flush=True)
            results.append({"model": model, "prompt": name, "verdict": "error", "detail": str(e)[:200]})

os.makedirs("results", exist_ok=True)
json.dump(results, open("results/toolshape_stream_ollama.json", "w"), indent=2)

print("\n=== SUMMARY (Ollama chat streaming; weather / search / event / parallel) ===", flush=True)
by_model = {}
for r in results:
    by_model.setdefault(r["model"], {})[r["prompt"]] = r["verdict"]
clean = 0
for m in MODELS:
    v = by_model.get(m, {})
    row = [v.get("weather", "-"), v.get("search", "-"), v.get("event", "-"), v.get("parallel", "-")]
    allclean = all(x == "clean_tool_calls" for x in row)
    clean += allclean
    print(f"  {m:<30} {'  '.join(x[:16] for x in row)}{'   [ALL CLEAN]' if allclean else ''}", flush=True)
print(f"\n{clean}/{len(MODELS)} models emit clean OpenAI tool_calls on all 4 streaming prompts (Ollama chat).", flush=True)
print("Saved results/toolshape_stream_ollama.json", flush=True)
