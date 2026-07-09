"""naive_json adapter — the dumb floor.

Plain ``json.loads`` on the stripped raw output. If the result is a dict with a
"name" key, treat it as a single tool call. If it is a list, map over its dict
items that carry a "name". On ANY exception, or when no name is present, return
``None``.

NO regex. NO repair. This adapter exists to mark the floor: it can only recover
a tool call that the model already emitted as valid JSON (corpus case 0001).
"""

from __future__ import annotations

import json
from typing import List, Optional

from .protocol import ToolCall


def _coerce(arguments: object) -> dict:
    """Return a dict for an ``arguments`` value.

    If ``arguments`` is a JSON string, parse it. If it is already a dict, keep
    it. Otherwise return an empty dict.
    """
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _one(d: dict) -> Optional[ToolCall]:
    name = d.get("name")
    if not isinstance(name, str) or not name:
        return None
    arguments = d.get("arguments")
    if arguments is None:
        arguments = d.get("parameters")
    return {"name": name, "arguments": _coerce(arguments or {})}


def adapter(raw_output: str, request_tools: List[str]) -> Optional[List[ToolCall]]:
    try:
        parsed = json.loads(raw_output.strip())
    except Exception:
        return None

    if isinstance(parsed, dict):
        call = _one(parsed)
        return [call] if call is not None else None

    if isinstance(parsed, list):
        calls = []
        for item in parsed:
            if isinstance(item, dict):
                call = _one(item)
                if call is not None:
                    calls.append(call)
        return calls or None

    return None
