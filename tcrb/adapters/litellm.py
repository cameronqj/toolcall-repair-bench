"""litellm adapter — a planned stub.

The scorer SKIPS stub adapters; the leaderboard lists them as planned. See
ROADMAP.
"""

from __future__ import annotations

from typing import List, Optional

from .protocol import ToolCall


def adapter(raw_output: str, request_tools: List[str]) -> Optional[List[ToolCall]]:
    raise NotImplementedError("litellm adapter is a planned stub — see ROADMAP")
