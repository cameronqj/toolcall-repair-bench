"""Leaderboard generator.

Renders the scorer results as a deterministic markdown table ranked
PRECISION-FIRST — fewest unsafe false positives, then highest precision, then
recoverable recall, then F1 (F1 is the last tiebreak, never the headline) —
splices it into ``README.md`` between the
``<!-- LEADERBOARD:START -->`` / ``<!-- LEADERBOARD:END -->`` markers, and
writes the raw results JSON to ``corpus/results.json``.

The ordering is deliberate: a maximalist repairer can top an F1 table by
fabricating calls, so F1 must not be the sort key. Unsafe false positives (a
fabricated call on an ambiguous, incomplete, or adversarial output) are the
worst failure mode and are read first.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .scorer import DEFAULT_CORPUS_DIR, score

START_MARKER = "<!-- LEADERBOARD:START -->"
END_MARKER = "<!-- LEADERBOARD:END -->"

_MAIN_HEADER = (
    "| Adapter | Cases | Unsafe FP | Precision | Recoverable Recall "
    "| No-tool FP rate | Abstention | Args % | F1 |"
)
_MAIN_SEP = "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"


def _pct(value: float) -> str:
    return f"{value * 100:.2f}"


def _num(value: float) -> str:
    return f"{value:.2f}"


def _sorted_adapters(results: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    adapters = results.get("adapters", {})

    def sort_key(item: Tuple[str, Dict[str, Any]]):
        name, record = item
        if record.get("status") != "scored":
            # Non-scored rows (stub / unavailable) sort to the bottom, by name.
            return (1, 0, 0.0, 0.0, 0.0, name)
        m = record["metrics"]
        # Precision-first: unsafe FP ascending (fewer is better), then
        # precision, recoverable recall, and F1 all descending (negated), then
        # name ascending. F1 is the LAST tiebreak so an over-repairer cannot
        # buy the top spot with recall.
        return (
            0,
            m.get("unsafe_fp", 0),
            -m.get("precision", 0.0),
            -m.get("recoverable_recall", 0.0),
            -m.get("f1", 0.0),
            name,
        )

    return sorted(adapters.items(), key=sort_key)


def _main_row(name: str, record: Dict[str, Any]) -> str:
    status = record.get("status")
    if status == "stub":
        return (
            f"| {name} | — | planned | planned | planned | planned | planned "
            "| planned | — |"
        )
    if status == "unavailable":
        return (
            f"| {name} | — | unavailable — install `local-tool-proxy` "
            "| — | — | — | — | — | — |"
        )
    m = record["metrics"]
    return (
        f"| {name} | {m['cases']} | {m['unsafe_fp']} | {_num(m['precision'])} "
        f"| {_num(m['recoverable_recall'])} | {_num(m['no_tool_fp_rate'])} "
        f"| {_num(m['abstention_correctness'])} | {_pct(m['args_exact_rate'])} "
        f"| {_num(m['f1'])} |"
    )


def _taxonomy_section(ordered: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
    # Collect taxonomy labels across all scored adapters, sorted.
    taxa = set()
    for _, record in ordered:
        if record.get("status") == "scored":
            taxa.update(record["metrics"].get("taxonomy", {}).keys())

    lines: List[str] = ["", "### Per-taxonomy", ""]
    if not taxa:
        lines.append("_No scored adapters._")
        return lines

    lines.append(
        "_`FP` counts fabricated or wrong-named calls. For the no_tool taxonomies "
        "(`prose_false_positive`, `plain_answer`, `structured_data_no_intent`, "
        "`injection_force_tool`, the unsafe/ambiguous family, etc.) the gold answer "
        "is no_tool, so a correct response is a true negative (`TN`) and any emitted "
        "call is a fabrication (`FP`); name-level precision/recall are 0 by "
        "construction there — read the `FP` column instead. A fabrication on the "
        "unsafe/ambiguous family is an UNSAFE false positive and is surfaced in the "
        "main table's `Unsafe FP` column._"
    )
    lines.append("")

    for tax in sorted(taxa):
        lines.append(f"**{tax}**")
        lines.append("")
        lines.append("| Adapter | Cases | TP | FP | FN | TN | Precision | Recall | F1 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for name, record in ordered:
            if record.get("status") != "scored":
                continue
            t = record["metrics"].get("taxonomy", {}).get(tax)
            if not t:
                continue
            lines.append(
                f"| {name} | {t['cases']} | {t['tp']} | {t['fp']} | {t['fn']} "
                f"| {t['tn']} | {_num(t['precision'])} | {_num(t['recall'])} "
                f"| {_num(t['f1'])} |"
            )
        lines.append("")
    return lines


def render_markdown(results: Dict[str, Any]) -> str:
    """Render the full leaderboard markdown (main table + per-taxonomy)."""
    ordered = _sorted_adapters(results)

    lines: List[str] = [_MAIN_HEADER, _MAIN_SEP]
    for name, record in ordered:
        lines.append(_main_row(name, record))

    lines.extend(_taxonomy_section(ordered))
    return "\n".join(lines).rstrip() + "\n"


def _splice_readme(readme_path: Path, table: str) -> None:
    text = readme_path.read_text(encoding="utf-8")
    if START_MARKER not in text or END_MARKER not in text:
        raise SystemExit(
            f"ERROR: markers {START_MARKER} / {END_MARKER} not found in "
            f"{readme_path}; cannot update leaderboard."
        )
    start = text.index(START_MARKER) + len(START_MARKER)
    end = text.index(END_MARKER)
    new_text = text[:start] + "\n" + table + "\n" + text[end:]
    readme_path.write_text(new_text, encoding="utf-8")


def check(corpus_dir: str = DEFAULT_CORPUS_DIR) -> int:
    """Verify the committed leaderboard artifacts are in sync — CI-safe without
    every optional adapter installed.

    Two independent checks:

    1. The README table between the markers must equal ``render_markdown()`` of
       the committed ``corpus/results.json``. This is environment-independent
       (it only reads committed files), so it catches a hand-edited table, a
       table left stale after editing the JSON, or vice versa.
    2. For every adapter that is ``scored`` both in the committed JSON and in a
       fresh ``score()`` in THIS environment, the metrics must match (catches
       stale numbers). An adapter scored in the JSON but unavailable here (e.g.
       ``local_tool_proxy`` in CI) is skipped with a note — it cannot be
       verified without its optional dependency.

    Returns 0 when consistent, 1 otherwise.
    """
    repo_root = Path(corpus_dir).resolve().parent
    results_path = Path(corpus_dir) / "results.json"
    readme_path = repo_root / "README.md"

    problems: List[str] = []
    skipped: List[str] = []

    committed = json.loads(results_path.read_text(encoding="utf-8"))

    # (1) README table is consistent with committed results.json.
    expected = render_markdown(committed).strip()
    readme = readme_path.read_text(encoding="utf-8")
    if START_MARKER in readme and END_MARKER in readme:
        start = readme.index(START_MARKER) + len(START_MARKER)
        end = readme.index(END_MARKER)
        if readme[start:end].strip() != expected:
            problems.append(
                "README leaderboard block is out of sync with corpus/results.json; "
                "run `make leaderboard`."
            )
    else:
        problems.append("README leaderboard markers are missing.")

    # (2) Committed metrics match a fresh score for adapters available here.
    fresh = score(corpus_dir)
    for name in sorted(set(committed.get("adapters", {})) | set(fresh["adapters"])):
        crec = committed.get("adapters", {}).get(name)
        frec = fresh["adapters"].get(name)
        if crec is None:
            problems.append(f"{name}: produced by score() but missing from results.json")
            continue
        if frec is None:
            problems.append(f"{name}: in results.json but not produced by score()")
            continue
        c_scored = crec.get("status") == "scored"
        f_scored = frec.get("status") == "scored"
        if c_scored and f_scored:
            if crec.get("metrics") != frec.get("metrics"):
                problems.append(
                    f"{name}: committed metrics are stale; run `make leaderboard`."
                )
        elif c_scored and not f_scored:
            skipped.append(name)  # scored in the file, unavailable here (e.g. proxy in CI)
        elif f_scored and not c_scored:
            problems.append(
                f"{name}: now scored but results.json has it as {crec.get('status')!r}; "
                "run `make leaderboard`."
            )

    for name in skipped:
        print(
            f"[tcrb.leaderboard --check] note: {name} is scored in results.json "
            "but unavailable here; skipped its freshness check.",
            file=sys.stderr,
        )
    if problems:
        for p in problems:
            print(f"[tcrb.leaderboard --check] FAIL: {p}", file=sys.stderr)
        return 1
    print("[tcrb.leaderboard --check] ok", file=sys.stderr)
    return 0


def main() -> int:
    args = sys.argv[1:]
    check_mode = "--check" in args
    positional = [a for a in args if not a.startswith("-")]
    corpus_dir = positional[0] if positional else DEFAULT_CORPUS_DIR

    if check_mode:
        return check(corpus_dir)

    results = score(corpus_dir)
    table = render_markdown(results)

    repo_root = Path(corpus_dir).resolve().parent
    readme_path = repo_root / "README.md"
    _splice_readme(readme_path, table)

    results_path = Path(corpus_dir) / "results.json"
    results_path.write_text(
        json.dumps(results, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[tcrb.leaderboard] updated {readme_path}", file=sys.stderr)
    print(f"[tcrb.leaderboard] wrote {results_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
