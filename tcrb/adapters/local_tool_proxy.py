"""local_tool_proxy adapter — imports the sibling repair library.

Constitution principle: adapters import upstream, they never fork it. This
module imports the ``local-tool-proxy`` library's parser and normalizes its
OpenAI-style output to the benchmark's plain ToolCall shape.

The sibling is installed separately (``pip install -e ../local-tool-proxy``). In CI
it is ABSENT — that is expected. When the import fails, ``AVAILABLE`` is set to
``False``, the adapter callable returns ``None``, and the registry marks the
entry unavailable so the scorer skips it and the leaderboard reports it as
needing the sibling installed.
"""

from __future__ import annotations

import json
from typing import List, Optional

from .protocol import ToolCall

try:
    from proxy.rewriters import (  # type: ignore
        extract_known_tool_names,  # noqa: F401  (part of the documented upstream surface)
        parse_tool_call_from_content,
    )

    AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when sibling is absent
    AVAILABLE = False
    parse_tool_call_from_content = None  # type: ignore


def _normalize(fn: dict) -> ToolCall:
    """Map one OpenAI-style ``function`` block to a plain ToolCall.

    Upstream returns ``arguments`` as a JSON string; parse it when so, else keep
    whatever dict it already is.
    """
    name = fn.get("name", "")
    arguments = fn.get("arguments", {})
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except (ValueError, TypeError):
            arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    return {"name": name, "arguments": arguments}


def adapter(raw_output: str, request_tools: List[str]) -> Optional[List[ToolCall]]:
    if not AVAILABLE or parse_tool_call_from_content is None:
        return None

    raw = parse_tool_call_from_content(raw_output, request_tools)
    if not raw:
        return None

    calls = []
    for item in raw:
        fn = item.get("function") if isinstance(item, dict) else None
        if isinstance(fn, dict):
            calls.append(_normalize(fn))
    return calls or None
