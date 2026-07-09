"""Adapter behavior tests against the seed corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from tcrb.adapters import greedy_name_match, instructor, litellm, naive_json, ollama_native
from tcrb.case import load_cases, tool_names

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = str(REPO_ROOT / "corpus")


def _cases_by_id():
    return {c.id: c for c in load_cases(CORPUS_DIR)}


CASES = _cases_by_id()
C1 = CASES["0001-json-in-content"]
C2 = CASES["0002-toolname-brace-json"]
C3 = CASES["0003-xml-tool-code"]
C4 = CASES["0004-prose-false-positive"]


def _run(fn, case):
    return fn(case.raw_output, tool_names(case))


# --- naive_json -----------------------------------------------------------

def test_naive_json_parses_0001():
    out = _run(naive_json.adapter, C1)
    assert out == [{"name": "write_file", "arguments": {"path": "buggy.py", "content": "fixed code here"}}]


@pytest.mark.parametrize("case", [C2, C3, C4], ids=lambda c: c.id)
def test_naive_json_none_on_others(case):
    assert _run(naive_json.adapter, case) is None


# --- greedy_name_match ----------------------------------------------------

@pytest.mark.parametrize(
    "case,name",
    [(C1, "write_file"), (C2, "run_terminal_cmd"), (C3, "run_command")],
    ids=["0001", "0002", "0003"],
)
def test_greedy_matches_name(case, name):
    out = _run(greedy_name_match.adapter, case)
    assert out == [{"name": name, "arguments": {}}]


def test_greedy_fabricates_on_prose():
    # Case 0004 is no_tool, but the prose mentions the tool name → fabricated call.
    out = _run(greedy_name_match.adapter, C4)
    assert out == [{"name": "write_file", "arguments": {}}]


# --- stubs ----------------------------------------------------------------

@pytest.mark.parametrize("stub", [litellm, ollama_native, instructor])
def test_stubs_raise(stub):
    with pytest.raises(NotImplementedError):
        stub.adapter("anything", ["write_file"])


# --- local_tool_proxy (gated on availability) -----------------------------

def test_local_tool_proxy_when_available():
    pytest.importorskip("proxy.rewriters")
    from tcrb.adapters import local_tool_proxy

    if not local_tool_proxy.AVAILABLE:
        pytest.skip("local-tool-proxy sibling not available")

    assert _run(local_tool_proxy.adapter, C1) == [
        {"name": "write_file", "arguments": {"path": "buggy.py", "content": "fixed code here"}}
    ]
    assert _run(local_tool_proxy.adapter, C2) == [
        {"name": "run_terminal_cmd", "arguments": {"command": "pytest -q"}}
    ]
    assert _run(local_tool_proxy.adapter, C3) == [
        {"name": "run_command", "arguments": {"command": "mkdir multi_tool_test"}}
    ]
    assert _run(local_tool_proxy.adapter, C4) is None
