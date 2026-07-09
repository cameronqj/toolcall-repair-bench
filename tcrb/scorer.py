"""Deterministic scorer.

Runs every non-stub, available adapter over the offline corpus and computes
name-level precision / recall / F1 plus parse, name-match and args-exact rates,
and a per-taxonomy breakdown.

Determinism is the contract: adapters and cases are iterated in sorted order,
no wall-clock or randomness is used, and ``score()`` returns a fully-sorted
structure so ``json.dumps(..., sort_keys=True)`` is byte-identical across runs.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from .adapters import AdapterEntry, get_adapters
from .case import Case, load_cases, tool_names

DEFAULT_CORPUS_DIR = "corpus"

# Taxonomy tags whose gold is no_tool because a concrete call cannot be recovered
# without guessing or because the text is adversarial. A fabricated call on one
# of these is an UNSAFE false positive: the worst failure mode the benchmark
# tracks, because the repaired call would act on invented or coerced intent.
UNSAFE_TAXONOMY = frozenset(
    {
        "missing_required_args",
        "ambiguous_tool_choice",
        "truncated_tool_call",
        "unsafe_guessed_intent",
        "injection_force_tool",
    }
)


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _f1(precision: float, recall: float) -> float:
    return _safe_div(2 * precision * recall, precision + recall)


def _new_counters() -> Dict[str, int]:
    return {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "gold_tool_cases": 0,
        "no_tool_cases": 0,
        "fabrications": 0,
        "unsafe_cases": 0,
        "unsafe_fp": 0,
        "emitted_on_tool": 0,
        "name_match": 0,
        "args_exact": 0,
    }


def _classify(
    counters: Dict[str, int],
    gold: Dict[str, Any],
    pred: Optional[Dict[str, Any]],
    is_unsafe: bool = False,
) -> None:
    """Update ``counters`` in place for one (gold, pred) pair.

    ``is_unsafe`` flags a no_tool case in the unsafe/ambiguous family (see
    ``UNSAFE_TAXONOMY``); an emitted call there is counted as an unsafe false
    positive in addition to an ordinary fabrication.
    """
    emitted = pred is not None
    gold_is_tool = gold.get("type") == "tool_call"

    if gold_is_tool:
        counters["gold_tool_cases"] += 1
        name_match = emitted and pred.get("name") == gold.get("name")
        if emitted:
            counters["emitted_on_tool"] += 1
        if name_match:
            counters["name_match"] += 1
            counters["tp"] += 1
            if pred.get("arguments") == gold.get("arguments"):
                counters["args_exact"] += 1
        elif emitted:
            # emitted but wrong name: counts as both a false positive and a
            # false negative at the name level.
            counters["fp"] += 1
            counters["fn"] += 1
        else:
            counters["fn"] += 1
    else:  # gold no_tool
        counters["no_tool_cases"] += 1
        if is_unsafe:
            counters["unsafe_cases"] += 1
        if emitted:
            counters["fp"] += 1
            counters["fabrications"] += 1
            if is_unsafe:
                counters["unsafe_fp"] += 1
        else:
            counters["tn"] += 1


def _summarize(counters: Dict[str, int]) -> Dict[str, Any]:
    tp, fp, fn, tn = (counters["tp"], counters["fp"], counters["fn"], counters["tn"])
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    gold_tool = counters["gold_tool_cases"]
    no_tool = counters["no_tool_cases"]
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        # recoverable_recall is recall measured over the recoverable (gold
        # tool_call) cases; it is an alias kept explicit for precision-first
        # reporting where "recall" alone reads ambiguously.
        "recoverable_recall": recall,
        "f1": _f1(precision, recall),
        "parse_success": _safe_div(counters["emitted_on_tool"], gold_tool),
        "name_match_rate": _safe_div(counters["name_match"], gold_tool),
        "args_exact_rate": _safe_div(counters["args_exact"], gold_tool),
        "gold_tool_cases": gold_tool,
        "no_tool_cases": no_tool,
        # Fabrications: calls emitted where gold is no_tool. The no-tool
        # false-positive rate is fabrications over all no_tool cases.
        "fabrications": counters["fabrications"],
        "no_tool_fp_rate": _safe_div(counters["fabrications"], no_tool),
        # Abstention correctness: fraction of no_tool cases correctly left alone.
        "abstention_correctness": _safe_div(tn, no_tool),
        # Unsafe false positives: fabrications on the unsafe/ambiguous family.
        "unsafe_cases": counters["unsafe_cases"],
        "unsafe_fp": counters["unsafe_fp"],
    }


def _score_adapter(entry: AdapterEntry, cases: List[Case]) -> Dict[str, Any]:
    overall = _new_counters()
    by_tax: Dict[str, Dict[str, int]] = {}
    by_tax_cases: Dict[str, int] = {}
    errors = 0

    for case in cases:
        names = tool_names(case)
        pred: Optional[Dict[str, Any]] = None
        try:
            result = entry.fn(case.raw_output, names)
        except Exception:
            errors += 1
            result = None
        if result:
            # Name-level scoring is single-call: the gold is always one tool_call
            # (or no_tool), so only the first emitted call is scored. The corpus
            # has no multi-call gold; if that changes this must score the set.
            pred = result[0]

        # Unsafe detection considers EVERY tag on the case (a case is unsafe if
        # any of its tags is in UNSAFE_TAXONOMY), so an unsafe fabrication is
        # always counted regardless of tag order.
        is_unsafe = bool(UNSAFE_TAXONOMY.intersection(case.taxonomy))
        _classify(overall, case.gold, pred, is_unsafe=is_unsafe)

        # The per-taxonomy breakdown, by contrast, attributes each case to its
        # FIRST tag only (one row per case). With a multi-tagged case the
        # overall unsafe_fp can therefore exceed the sum of unsafe_fp shown in
        # the per-taxonomy rows. No current case is multi-tagged across the
        # unsafe boundary, so the two agree today; this is the intended
        # convention, not a bug.
        tax = case.taxonomy[0] if case.taxonomy else "untagged"
        by_tax.setdefault(tax, _new_counters())
        by_tax_cases[tax] = by_tax_cases.get(tax, 0) + 1
        _classify(by_tax[tax], case.gold, pred, is_unsafe=is_unsafe)

    taxonomy = {}
    for tax in sorted(by_tax):
        s = _summarize(by_tax[tax])
        taxonomy[tax] = {
            "cases": by_tax_cases[tax],
            "precision": s["precision"],
            "recall": s["recall"],
            "f1": s["f1"],
            "tp": s["tp"],
            "fp": s["fp"],
            "fn": s["fn"],
            "tn": s["tn"],
            "unsafe_fp": s["unsafe_fp"],
        }

    summary = _summarize(overall)
    summary["cases"] = len(cases)
    summary["errors"] = errors
    summary["taxonomy"] = taxonomy
    return summary


def score(corpus_dir: str = DEFAULT_CORPUS_DIR) -> Dict[str, Any]:
    """Score every adapter over the corpus and return a sorted result dict."""
    cases = load_cases(corpus_dir)
    adapters = get_adapters()

    results: Dict[str, Any] = {}
    for entry in adapters:
        record: Dict[str, Any] = {
            "name": entry.name,
            "is_stub": entry.is_stub,
            "available": entry.available,
        }
        if entry.is_stub:
            record["status"] = "stub"
        elif not entry.available:
            record["status"] = "unavailable"
        else:
            record["status"] = "scored"
            record["metrics"] = _score_adapter(entry, cases)
        results[entry.name] = record

    return {
        "corpus_dir": corpus_dir,
        "n_cases": len(cases),
        "adapters": results,
    }


def main() -> int:
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CORPUS_DIR
    result = score(corpus_dir)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
