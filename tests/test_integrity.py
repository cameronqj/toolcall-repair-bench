"""Corpus and reporting integrity checks.

Covers the cross-case invariants the JSON Schema cannot express, and the clean
representation of adapters that are unavailable (e.g. the optional sibling
library is not installed).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from tcrb.case import load_cases
from tcrb.leaderboard import _sorted_adapters, render_markdown
from tcrb.schema_validate import check_integrity, validate_corpus
from tcrb.scorer import score

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = str(REPO_ROOT / "corpus")

# no_tool taxonomies that assert "the model did NOT make a call". A clean,
# complete, parseable call to an OFFERED tool contradicts these labels (it is a
# recoverable tool_call). The unsafe/ambiguous family is deliberately excluded:
# those are gold no_tool even when a parseable call exists (abstaining is the
# point), and unknown_tool_near_match is about names that were never offered.
NATURAL_NO_TOOL_TAXONOMY = frozenset(
    {
        "prose_false_positive",
        "plain_answer",
        "clarifying_question",
        "literal_commands",
        "code_snippet_mention",
        "documentation_example",
        "structured_data_no_intent",
    }
)

_NAME_KEYS = ("name", "tool_name")
_ARG_KEYS = ("arguments", "parameters", "params")


def _parse_single_call(raw):
    """Return (name, args) if ``raw`` is a single JSON object that looks like a
    tool call (a non-empty name-like key plus an args-like dict), else None.

    Tolerates the field-name variants seen in captured output (``parameters`` /
    ``params`` for ``arguments``; ``tool_name`` for ``name``) so the check
    catches the exact mislabel class that motivated it.
    """
    try:
        obj = json.loads(raw.strip())
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    name = next(
        (obj[k] for k in _NAME_KEYS if isinstance(obj.get(k), str) and obj.get(k)),
        None,
    )
    if name is None:
        return None
    args = next((obj[k] for k in _ARG_KEYS if isinstance(obj.get(k), dict)), {})
    return name, args


def _required_args(case, name):
    for tool in case.request_tools:
        if tool.get("name") == name:
            return tool.get("parameters", {}).get("required", []) or []
    return []


def test_real_corpus_is_internally_consistent():
    # 0 means every case validates AND all integrity invariants hold.
    assert validate_corpus(CORPUS_DIR) == 0


def test_public_corpus_cases_do_not_leak_local_absolute_paths():
    forbidden = ("/" + "home/ubuntu/projects/toolcall-repair-bench", "/" + "home/ubuntu")
    for path in sorted((REPO_ROOT / "corpus" / "cases").glob("*.json")):
        text = path.read_text(encoding="utf-8")
        assert not any(s in text for s in forbidden), path.name

        data = json.loads(text)
        prov = data["provenance"]
        if prov["kind"] == "captured":
            assert prov["model"] != "synthetic"
            source = prov.get("source", "")
            assert not source.startswith("/")
        else:
            assert prov["kind"] == "synthetic"
            assert prov["model"] == "synthetic"


def test_tracked_files_do_not_leak_private_network_identifiers():
    """No tracked text file may contain a private-LAN IP or a /home|/Users home path.

    The corpus and the findings/ scripts are captured from a homelab; a private
    address or absolute home path published in a CC-BY-4.0 corpus is redistributed
    forever. This scans everything tracked except tests/ (which legitimately holds
    example patterns like this one, kept split so it does not self-match).
    """
    priv_ip = re.compile(
        r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
        r"|192\.168\.\d{1,3}\.\d{1,3}"
        r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
    )
    home = re.compile(r"/(?:" + "home|Users" + r")/[a-z_][a-z0-9_-]+/")
    text_ext = {".py", ".md", ".json", ".txt", ".toml", ".cfg", ".ini",
                ".yml", ".yaml", ".sh", ".mk", ""}

    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()

    offenders = []
    for rel in tracked:
        if rel.startswith("tests/"):
            continue
        path = REPO_ROOT / rel
        if path.suffix.lower() not in text_ext:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if priv_ip.search(text) or home.search(text):
            offenders.append(rel)
    assert not offenders, f"private-network identifiers leaked in: {offenders}"


def test_integrity_catches_duplicate_ids():
    case = {"id": "dup", "gold": {"type": "no_tool"}, "request_tools": []}
    errors = check_integrity([("dup.json", case), ("dup.json", case)])
    assert any("duplicate id" in e for e in errors)


def test_integrity_catches_id_filename_mismatch():
    case = {"id": "actual-id", "gold": {"type": "no_tool"}, "request_tools": []}
    errors = check_integrity([("different-name.json", case)])
    assert any("does not match filename" in e for e in errors)


def test_integrity_catches_gold_name_not_offered():
    case = {
        "id": "x-y",
        "gold": {"type": "tool_call", "name": "ghost", "arguments": {}},
        "request_tools": [{"name": "real_tool"}],
    }
    errors = check_integrity([("x-y.json", case)])
    assert any("not in request_tools" in e for e in errors)


_CAPTURED_PROV = {"kind": "captured", "model": "gemma4:e4b-mlx"}
_SYNTHETIC_PROV = {"kind": "synthetic", "model": "synthetic", "synthetic": True}


def test_integrity_passes_on_well_formed_cases():
    cases = [
        (
            "a.json",
            {
                "id": "a",
                "provenance": _SYNTHETIC_PROV,
                "gold": {"type": "no_tool"},
                "request_tools": [],
            },
        ),
        (
            "b.json",
            {
                "id": "b",
                "provenance": _CAPTURED_PROV,
                "gold": {"type": "tool_call", "name": "t", "arguments": {}},
                "request_tools": [{"name": "t"}],
            },
        ),
    ]
    assert check_integrity(cases) == []


def test_integrity_requires_provenance_kind():
    case = {
        "id": "x",
        "provenance": {"model": "gemma4:e4b-mlx"},  # no kind
        "gold": {"type": "no_tool"},
        "request_tools": [],
    }
    errors = check_integrity([("x.json", case)])
    assert any("provenance.kind" in e for e in errors)


def test_integrity_catches_synthetic_flag_disagreeing_with_kind():
    case = {
        "id": "x",
        "provenance": {"kind": "captured", "model": "gemma4:e4b-mlx", "synthetic": True},
        "gold": {"type": "no_tool"},
        "request_tools": [],
    }
    errors = check_integrity([("x.json", case)])
    assert any("disagrees with" in e for e in errors)


def test_integrity_catches_captured_labeled_synthetic_model():
    case = {
        "id": "x",
        "provenance": {"kind": "captured", "model": "synthetic"},
        "gold": {"type": "no_tool"},
        "request_tools": [],
    }
    errors = check_integrity([("x.json", case)])
    assert any("must name a real model" in e for e in errors)


def test_integrity_catches_synthetic_without_synthetic_model():
    case = {
        "id": "x",
        "provenance": {"kind": "synthetic", "model": "gemma4:e4b-mlx"},
        "gold": {"type": "no_tool"},
        "request_tools": [],
    }
    errors = check_integrity([("x.json", case)])
    assert any("must set provenance.model to" in e for e in errors)


def test_unavailable_adapter_renders_cleanly():
    # An unavailable adapter (optional dependency absent) must render as a clean
    # row, not crash or look like a zero score.
    results = {
        "adapters": {
            "local_tool_proxy": {
                "name": "local_tool_proxy",
                "is_stub": False,
                "available": False,
                "status": "unavailable",
            }
        }
    }
    md = render_markdown(results)
    assert "local_tool_proxy" in md
    assert "unavailable" in md


def _scored(name, **metrics):
    base = {
        "unsafe_fp": 0,
        "precision": 0.0,
        "recoverable_recall": 0.0,
        "f1": 0.0,
    }
    base.update(metrics)
    return name, {"name": name, "is_stub": False, "available": True,
                  "status": "scored", "metrics": base}


def test_ranking_is_precision_first_not_f1():
    # An over-repairer with the highest F1 but unsafe false positives must rank
    # BELOW a safer adapter with lower F1 and zero unsafe FP.
    greedy = _scored("greedy", unsafe_fp=5, precision=0.58, recoverable_recall=1.0, f1=0.73)
    safe = _scored("safe", unsafe_fp=0, precision=0.80, recoverable_recall=0.53, f1=0.62)
    results = {"adapters": dict([greedy, safe])}
    order = [name for name, _ in _sorted_adapters(results)]
    assert order == ["safe", "greedy"]


def test_ranking_breaks_unsafe_ties_by_precision():
    a = _scored("a", unsafe_fp=2, precision=0.50, recoverable_recall=0.2, f1=0.29)
    b = _scored("b", unsafe_fp=2, precision=0.73, recoverable_recall=0.53, f1=0.62)
    results = {"adapters": dict([a, b])}
    order = [name for name, _ in _sorted_adapters(results)]
    assert order == ["b", "a"]


def test_ranking_is_deterministic():
    a = _scored("a", unsafe_fp=1, precision=0.5, recoverable_recall=0.5, f1=0.5)
    b = _scored("b", unsafe_fp=1, precision=0.5, recoverable_recall=0.5, f1=0.5)
    results = {"adapters": dict([b, a])}
    # Identical metrics -> stable tiebreak on name, regardless of input order.
    assert [n for n, _ in _sorted_adapters(results)] == ["a", "b"]


def test_scored_adapters_rank_above_non_scored():
    scored = _scored("zzz_scored", unsafe_fp=9, precision=0.1)
    stub = ("aaa_stub", {"name": "aaa_stub", "is_stub": True, "available": True,
                         "status": "stub"})
    results = {"adapters": dict([stub, scored])}
    order = [name for name, _ in _sorted_adapters(results)]
    # Even a weak scored adapter ranks above a stub/unavailable row.
    assert order == ["zzz_scored", "aaa_stub"]


def test_stub_adapter_renders_as_planned():
    results = {
        "adapters": {
            "litellm": {
                "name": "litellm",
                "is_stub": True,
                "available": True,
                "status": "stub",
            }
        }
    }
    md = render_markdown(results)
    assert "litellm" in md
    assert "planned" in md


# --- Label / data / doc integrity guards (regression coverage for the
# parameters-vs-arguments mislabel class and the 37-vs-117 doc drift). ---


def test_no_natural_no_tool_case_is_a_clean_recoverable_call():
    """A no_tool case in a "the model made no call" taxonomy must not actually
    be a clean, complete, parseable call to an offered tool.

    This is the exact bug that mislabeled 0081/0082/0085/0089/0092/0098/0102:
    a single JSON object naming an offered tool with all required arguments
    present, promoted as prose_false_positive / no_tool.
    """
    offenders = []
    for case in load_cases(CORPUS_DIR):
        if case.gold.get("type") != "no_tool":
            continue
        # Unsafe/ambiguous family is intentionally no_tool even with a parseable
        # call; only the "natural language, no call" taxonomies are contradicted.
        if not NATURAL_NO_TOOL_TAXONOMY.intersection(case.taxonomy):
            continue
        parsed = _parse_single_call(case.raw_output)
        if not parsed:
            continue
        name, args = parsed
        offered = {t.get("name") for t in case.request_tools}
        if name not in offered:
            continue  # a non-offered name is legitimately no_tool
        required = _required_args(case, name)
        all_present = all(args.get(r) not in (None, "", {}, []) for r in required)
        if all_present:
            offenders.append(case.id)
    assert not offenders, (
        "no_tool cases that are actually clean recoverable calls to an offered "
        f"tool (should be gold tool_call): {offenders}"
    )


def test_unknown_tool_near_match_names_an_unoffered_tool():
    """A case tagged unknown_tool_near_match must emit a name that was NOT
    offered; otherwise it is a recoverable call, not a near-match (cf. 0098)."""
    for case in load_cases(CORPUS_DIR):
        if "unknown_tool_near_match" not in case.taxonomy:
            continue
        parsed = _parse_single_call(case.raw_output)
        if not parsed:
            continue
        name, _ = parsed
        offered = {t.get("name") for t in case.request_tools}
        assert name not in offered, (
            f"{case.id}: tagged unknown_tool_near_match but emitted name "
            f"{name!r} IS an offered tool — it is a recoverable call"
        )


def test_notes_do_not_deny_a_parseable_call_that_exists():
    """A note must not claim there is no parseable tool call when raw_output
    parses to one. Guards the false boilerplate notes (cf. 0082)."""
    false_phrases = ("no committed, parseable tool call", "contains no committed")
    for case in load_cases(CORPUS_DIR):
        if not case.note or not _parse_single_call(case.raw_output):
            continue
        low = case.note.lower()
        assert not any(p in low for p in false_phrases), (
            f"{case.id}: note denies a parseable call, but raw_output parses to one"
        )


def test_committed_results_match_fresh_score_for_deterministic_adapters():
    """corpus/results.json must not go stale for the pure-Python adapters.

    Scoped to naive_json / greedy_name_match because they are always available
    and fully deterministic; the local_tool_proxy row depends on the sibling
    library's version and is not asserted here (it is pinned in the docs)."""
    committed = json.loads((REPO_ROOT / "corpus" / "results.json").read_text("utf-8"))
    fresh = score(CORPUS_DIR)
    for name in ("naive_json", "greedy_name_match"):
        assert committed["adapters"][name] == fresh["adapters"][name], (
            f"committed corpus/results.json is stale for {name}; run "
            "`make leaderboard` and commit the result"
        )


def test_doc_counts_match_corpus_size():
    """README.md and corpus/README.md must state the real corpus size and not
    the stale 37-case count."""
    total = len(load_cases(CORPUS_DIR))
    for rel in ("README.md", "corpus/README.md"):
        text = (REPO_ROOT / rel).read_text("utf-8")
        assert f"{total} cases" in text, f"{rel} does not state '{total} cases'"
        assert "37 cases" not in text, f"{rel} still references the stale '37 cases'"


def test_leaderboard_check_passes_on_committed_artifacts():
    """The committed README table and corpus/results.json must be in sync."""
    from tcrb.leaderboard import check

    assert check(CORPUS_DIR) == 0


def test_leaderboard_check_detects_stale_metrics(tmp_path):
    """A self-contained copy passes, then fails once results.json is tampered."""
    import shutil

    from tcrb.leaderboard import check

    shutil.copytree(REPO_ROOT / "corpus", tmp_path / "corpus")
    shutil.copy(REPO_ROOT / "README.md", tmp_path / "README.md")
    cdir = str(tmp_path / "corpus")
    assert check(cdir) == 0

    rp = tmp_path / "corpus" / "results.json"
    data = json.loads(rp.read_text("utf-8"))
    data["adapters"]["naive_json"]["metrics"]["precision"] = 0.123456
    rp.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", "utf-8")
    assert check(cdir) == 1
