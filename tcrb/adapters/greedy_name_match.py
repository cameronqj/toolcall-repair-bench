"""greedy_name_match adapter — a documented MAXIMALIST STRAWMAN baseline.

This is an intentionally reckless baseline that demonstrates the
precision/recall frontier. For each offered tool name (in the given order), if
that name appears anywhere as a substring of the raw output, it fabricates a
call to the FIRST such name with EMPTY arguments.

Because it greps for tool names, it FABRICATES a tool call whenever a tool name
merely appears in prose (e.g. corpus case 0004, where the model says "I will
write_file ..." but makes no call). It trades precision for recall: it matches
the name on every genuine call but also hallucinates calls on plain prose, and
it never recovers arguments. It is here to mark the opposite extreme from
``naive_json`` and make the frontier visible on the leaderboard.
"""

from __future__ import annotations

from typing import List, Optional

from .protocol import ToolCall


def adapter(raw_output: str, request_tools: List[str]) -> Optional[List[ToolCall]]:
    for name in request_tools:
        if name and name in raw_output:
            return [{"name": name, "arguments": {}}]
    return None
