"""The adapter contract.

An adapter is a thin shim over a tool-call repair strategy. It takes the exact
raw string a model emitted plus the list of tool NAMES that were offered, and
returns the repaired tool call(s) or ``None``.

This module is intentionally dependency-free: it defines only the types and the
registry-entry record. Concrete adapters live in sibling modules and import
their upstream library; they never reimplement it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, runtime_checkable

# A repaired tool call. Deliberately a plain dict so adapters and the scorer
# never disagree about a class identity across import boundaries.
#   {"name": str, "arguments": dict}
ToolCall = Dict[str, object]


@runtime_checkable
class Adapter(Protocol):
    """Callable contract every adapter implements.

    Signature::

        (raw_output: str, request_tools: list[str]) -> list[ToolCall] | None

    ``request_tools`` is the list of tool NAMES offered in the request (the
    scorer derives these from each case's ``request_tools[].name``). Returning
    ``None`` or ``[]`` means "no tool call".
    """

    def __call__(
        self, raw_output: str, request_tools: List[str]
    ) -> Optional[List[ToolCall]]:
        ...


@dataclass(frozen=True)
class AdapterEntry:
    """A single registry entry.

    Attributes:
        name: Stable adapter name (used for sorting and reporting).
        fn: The adapter callable.
        is_stub: True if the adapter is a planned placeholder that raises
            ``NotImplementedError``; the scorer SKIPS these.
        available: False if the adapter's upstream dependency is absent; the
            scorer SKIPS these but the leaderboard lists them as unavailable.
    """

    name: str
    fn: Adapter
    is_stub: bool = False
    available: bool = True


AdapterFn = Callable[[str, List[str]], Optional[List[ToolCall]]]
