"""Capture scaffold — turn a raw local-model output into a PENDING case.

This is a deliberately small, NON-NETWORK helper. It reads a raw model-output
string (from a file or stdin) plus provenance metadata flags and writes a
*pending* case JSON under ``corpus/pending/`` for a human to label and promote.

It does NOT:
  - make any network call or require an API key (it reads a file you already
    captured);
  - auto-label the case (``taxonomy`` is left empty and ``gold`` is left unset);
  - touch ``corpus/cases/`` (pending drafts may still contain unsanitized text).

Promotion is a human step: review the raw output, sanitize secrets / local paths
/ private code (see SECURITY.md), choose the taxonomy and the defensible gold
label, then move the file into ``corpus/cases/`` and run ``make validate``.

Usage::

    python3 -m tcrb.capture --id 0042-qwen-fenced-json \\
        --model qwen2.5-coder:7b --runtime ollama --harness opencode \\
        --raw path/to/output.txt

    some_command | python3 -m tcrb.capture --id 0042-qwen-fenced-json \\
        --model qwen2.5-coder:7b --runtime ollama --raw -
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PENDING_NOTE = (
    "PENDING — human review required. Sanitize the raw_output, choose taxonomy "
    "tag(s) from the schema enum, and set a gold label that is defensible from "
    "raw_output alone. Then move this file into corpus/cases/ and run "
    "`make validate`."
)


def build_pending_case(
    case_id: str,
    raw_output: str,
    model: str,
    *,
    runtime: Optional[str] = None,
    harness: Optional[str] = None,
    prompt_id: Optional[str] = None,
    temperature: Optional[str] = None,
    captured: Optional[str] = None,
    source: Optional[str] = None,
    request_tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return a pending-case dict. Never auto-labels; gold is intentionally absent.

    The result carries ``_pending: true`` and an empty ``taxonomy``/``gold``
    placeholder, so it does NOT validate against the strict case schema until a
    human completes it. Deterministic: no clock or randomness is read here (pass
    ``captured`` explicitly for a dated case).
    """
    provenance: Dict[str, Any] = {"kind": "captured", "model": model}
    if runtime:
        provenance["runtime"] = runtime
    if harness:
        provenance["harness"] = harness
    if prompt_id:
        provenance["prompt_id"] = prompt_id
    if temperature is not None:
        provenance["temperature"] = temperature
    if captured:
        provenance["captured"] = captured
    provenance["source"] = source or "captured local-model output (pending review)"

    return {
        "_pending": True,
        "id": case_id,
        "provenance": provenance,
        "request_tools": request_tools or [],
        "raw_output": raw_output,
        "taxonomy": [],
        "gold": None,
        "note": PENDING_NOTE,
    }


def _read_raw(raw_arg: str) -> str:
    if raw_arg == "-":
        return sys.stdin.read()
    return Path(raw_arg).read_text(encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tcrb.capture",
        description="Scaffold a PENDING captured case (no network, no auto-label).",
    )
    p.add_argument("--id", required=True, help="Case id / filename stem, e.g. 0042-qwen-fenced-json.")
    p.add_argument("--raw", required=True, help="Path to the raw model-output file, or '-' for stdin.")
    p.add_argument("--model", required=True, help="The model that produced the output, e.g. qwen2.5-coder:7b.")
    p.add_argument("--runtime", help="Inference runtime, e.g. ollama / mlx / llama.cpp.")
    p.add_argument("--harness", help="Client/harness, e.g. opencode / openai-compatible.")
    p.add_argument("--prompt-id", dest="prompt_id", help="Stable prompt/task identifier.")
    p.add_argument("--temperature", help="Decoding temperature, if known.")
    p.add_argument("--captured", help="ISO date the output was captured (YYYY-MM-DD).")
    p.add_argument("--source", help="Free-text origin description.")
    p.add_argument("--out", default="corpus/pending", help="Output directory (default: corpus/pending).")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    raw = _read_raw(args.raw)
    case = build_pending_case(
        args.id,
        raw,
        args.model,
        runtime=args.runtime,
        harness=args.harness,
        prompt_id=args.prompt_id,
        temperature=args.temperature,
        captured=args.captured,
        source=args.source,
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.id}.json"
    out_path.write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")

    print(f"[tcrb.capture] wrote pending case {out_path}", file=sys.stderr)
    print(
        "[tcrb.capture] NEXT: sanitize raw_output, set taxonomy + gold, then move "
        "into corpus/cases/ and run `make validate`.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
