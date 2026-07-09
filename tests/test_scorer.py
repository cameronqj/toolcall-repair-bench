"""Scorer math, on a controlled synthetic corpus.

These tests build a tiny corpus in a temp directory with known cases so the
asserted numbers do not drift as the real corpus grows. They pin the two
behaviors the benchmark exists to measure:

  - a recoverable malformed case REWARDS correct tool/args repair (true positive),
  - a no_tool case PENALIZES false-positive repair (fabrication is a false positive).

Only the deterministic, dependency-free adapters (naive_json, greedy_name_match)
are asserted here. The real corpus is checked separately for internal
consistency, not for exact magic numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tcrb.case import load_cases
from tcrb.scorer import score

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = str(REPO_ROOT / "corpus")

# A controlled four-case corpus exercising both axes.
_SYNTHETIC_CASES = [
    {
        # Clean JSON-in-content: naive_json recovers it exactly.
        "id": "s1-clean-json",
        "provenance": {"model": "synthetic", "source": "test"},
        "request_tools": [{"name": "alpha"}],
        "raw_output": '{"name": "alpha", "arguments": {"x": "1"}}',
        "taxonomy": ["json_in_content"],
        "gold": {"type": "tool_call", "name": "alpha", "arguments": {"x": "1"}},
    },
    {
        # No-tool, but the prose names the tool: bait for a maximalist repairer.
        "id": "s2-no-tool-bait",
        "provenance": {"model": "synthetic", "source": "test"},
        "request_tools": [{"name": "alpha"}],
        "raw_output": "I might use alpha later, but not now.",
        "taxonomy": ["prose_false_positive"],
        "gold": {"type": "no_tool"},
    },
    {
        # No-tool, plain answer, tool name absent: everyone should abstain.
        "id": "s3-no-tool-plain",
        "provenance": {"model": "synthetic", "source": "test"},
        "request_tools": [{"name": "alpha"}],
        "raw_output": "The answer is 42.",
        "taxonomy": ["plain_answer"],
        "gold": {"type": "no_tool"},
    },
    {
        # Malformed-but-recoverable (single quotes): naive_json misses it,
        # greedy still name-matches.
        "id": "s4-brace-json",
        "provenance": {"model": "synthetic", "source": "test"},
        "request_tools": [{"name": "alpha"}],
        "raw_output": "alpha{'x': '2'}",
        "taxonomy": ["toolName_brace_json"],
        "gold": {"type": "tool_call", "name": "alpha", "arguments": {"x": "2"}},
    },
]


@pytest.fixture(scope="module")
def synthetic_results(tmp_path_factory):
    corpus = tmp_path_factory.mktemp("corpus")
    cases = corpus / "cases"
    cases.mkdir()
    for case in _SYNTHETIC_CASES:
        (cases / f"{case['id']}.json").write_text(json.dumps(case), encoding="utf-8")
    return score(str(corpus))


def _metrics(results, name):
    rec = results["adapters"][name]
    assert rec["status"] == "scored", f"{name} not scored: {rec['status']}"
    return rec["metrics"]


def test_recoverable_rewards_correct_repair(synthetic_results):
    # naive_json recovers s1 exactly (name + args), misses s4 (single quotes).
    m = _metrics(synthetic_results, "naive_json")
    assert m["tp"] == 1
    assert m["fp"] == 0  # never fabricates on the two no_tool cases
    assert m["fn"] == 1  # s4 not recovered
    assert m["tn"] == 2  # s2 and s3 correctly abstained
    assert m["precision"] == 1.0
    assert m["recall"] == 0.5
    assert m["args_exact_rate"] == 0.5  # 1 of 2 gold tool_call cases


def test_no_tool_penalizes_false_positive(synthetic_results):
    # greedy fabricates on s2 (no_tool but names the tool) -> a false positive.
    m = _metrics(synthetic_results, "greedy_name_match")
    assert m["tp"] == 2  # s1 and s4 name-matched
    assert m["fp"] == 1  # s2 fabrication
    assert m["fn"] == 0
    assert m["tn"] == 1  # s3 correctly abstained (tool name absent)
    assert m["precision"] == pytest.approx(2 / 3)
    assert m["recall"] == 1.0
    assert m["args_exact_rate"] == 0.0  # greedy always emits empty args


def test_confusion_matrix_accounts_for_every_case(synthetic_results):
    n = len(_SYNTHETIC_CASES)
    for name in ("naive_json", "greedy_name_match"):
        m = _metrics(synthetic_results, name)
        # Each case lands in exactly one bucket, except an emitted-but-wrong-name
        # case which is both FP and FN. The synthetic corpus has no such case.
        assert m["tp"] + m["fp"] + m["fn"] + m["tn"] == n


def test_f1_consistency(synthetic_results):
    for name in ("naive_json", "greedy_name_match"):
        m = _metrics(synthetic_results, name)
        p, r = m["precision"], m["recall"]
        expected = 0.0 if (p + r) == 0 else 2 * p * r / (p + r)
        assert m["f1"] == pytest.approx(expected)


# --- unsafe false positives + abstention -----------------------------------

# A second controlled corpus focused on the precision-first metrics: one
# recoverable case, one UNSAFE no_tool case (a parseable call missing a required
# arg), and one plain no_tool case everyone should abstain on.
_UNSAFE_CASES = [
    {
        "id": "u1-recoverable",
        "provenance": {"kind": "synthetic", "model": "synthetic"},
        "request_tools": [{"name": "alpha"}],
        "raw_output": '{"name": "alpha", "arguments": {"x": "1"}}',
        "taxonomy": ["json_in_content"],
        "gold": {"type": "tool_call", "name": "alpha", "arguments": {"x": "1"}},
    },
    {
        "id": "u2-missing-required",
        "provenance": {"kind": "synthetic", "model": "synthetic"},
        "request_tools": [{"name": "alpha"}],
        # Parses as JSON and names alpha, but carries no arguments: an unsafe
        # repair would invent the required argument.
        "raw_output": '{"name": "alpha"}',
        "taxonomy": ["missing_required_args"],
        "gold": {"type": "no_tool"},
    },
    {
        "id": "u3-plain-no-tool",
        "provenance": {"kind": "synthetic", "model": "synthetic"},
        "request_tools": [{"name": "alpha"}],
        "raw_output": "There is no call to make here.",
        "taxonomy": ["plain_answer"],
        "gold": {"type": "no_tool"},
    },
]


@pytest.fixture(scope="module")
def unsafe_results(tmp_path_factory):
    corpus = tmp_path_factory.mktemp("unsafe_corpus")
    cases = corpus / "cases"
    cases.mkdir()
    for case in _UNSAFE_CASES:
        (cases / f"{case['id']}.json").write_text(json.dumps(case), encoding="utf-8")
    return score(str(corpus))


@pytest.mark.parametrize("name", ["naive_json", "greedy_name_match"])
def test_unsafe_false_positive_is_counted(unsafe_results, name):
    # Both adapters fabricate a call on the missing-required-arg case, which is
    # in the unsafe family -> exactly one unsafe false positive surfaces.
    m = _metrics(unsafe_results, name)
    assert m["no_tool_cases"] == 2
    assert m["unsafe_cases"] == 1
    assert m["unsafe_fp"] == 1
    assert m["fabrications"] == 1
    # One of two no_tool cases correctly abstained.
    assert m["abstention_correctness"] == pytest.approx(0.5)
    assert m["no_tool_fp_rate"] == pytest.approx(0.5)


def test_recoverable_recall_aliases_recall(unsafe_results):
    for name in ("naive_json", "greedy_name_match"):
        m = _metrics(unsafe_results, name)
        assert m["recoverable_recall"] == m["recall"]


def test_stubs_are_skipped(synthetic_results):
    for name in ("litellm", "ollama_native", "instructor"):
        rec = synthetic_results["adapters"][name]
        assert rec["is_stub"] is True
        assert rec["status"] == "stub"
        assert "metrics" not in rec


# --- light invariants on the real corpus (no magic numbers) ----------------

@pytest.fixture(scope="module")
def real_results():
    return score(CORPUS_DIR)


def test_real_corpus_every_available_adapter_scored(real_results):
    n_cases = len(load_cases(CORPUS_DIR))
    assert real_results["n_cases"] == n_cases
    for _name, rec in real_results["adapters"].items():
        if rec["is_stub"] or not rec["available"]:
            assert "metrics" not in rec
            continue
        m = rec["metrics"]
        assert m["cases"] == n_cases
        # No case is lost: TP + FP* + FN* + TN covers every case (a wrong-name
        # emission counts in both FP and FN, so the sum is a lower bound).
        assert m["tp"] + m["fp"] + m["fn"] + m["tn"] >= n_cases
        assert 0.0 <= m["precision"] <= 1.0
        assert 0.0 <= m["recall"] <= 1.0
