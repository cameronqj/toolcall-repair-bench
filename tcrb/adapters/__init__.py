"""Adapter registry.

Builds a deterministic, name-sorted registry of every adapter together with its
flags (``is_stub``, ``available``). ``get_adapters()`` returns them sorted by
name so all downstream iteration is deterministic.
"""

from __future__ import annotations

from typing import List

from . import (
    greedy_name_match,
    instructor,
    litellm,
    local_tool_proxy,
    naive_json,
    ollama_native,
)
from .protocol import Adapter, AdapterEntry, ToolCall

__all__ = ["Adapter", "AdapterEntry", "ToolCall", "get_adapters"]


def _build_registry() -> List[AdapterEntry]:
    entries = [
        AdapterEntry(
            name="naive_json",
            fn=naive_json.adapter,
            is_stub=False,
            available=True,
        ),
        AdapterEntry(
            name="greedy_name_match",
            fn=greedy_name_match.adapter,
            is_stub=False,
            available=True,
        ),
        AdapterEntry(
            name="local_tool_proxy",
            fn=local_tool_proxy.adapter,
            is_stub=False,
            available=local_tool_proxy.AVAILABLE,
        ),
        AdapterEntry(
            name="litellm",
            fn=litellm.adapter,
            is_stub=True,
            available=True,
        ),
        AdapterEntry(
            name="ollama_native",
            fn=ollama_native.adapter,
            is_stub=True,
            available=True,
        ),
        AdapterEntry(
            name="instructor",
            fn=instructor.adapter,
            is_stub=True,
            available=True,
        ),
    ]
    return sorted(entries, key=lambda e: e.name)


def get_adapters() -> List[AdapterEntry]:
    """Return all adapter entries in deterministic, name-sorted order."""
    return _build_registry()
