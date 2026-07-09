"""Case loader.

Reads every ``*.json`` under ``corpus/cases/`` in filename-sorted order and
returns ``Case`` dataclasses. Loading is loud: the count is logged to stderr,
and any file that fails to parse is skipped AND logged (no silent drops —
constitution principle 9).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Case:
    """One corpus case (see corpus/schema/case.schema.json)."""

    id: str
    provenance: Dict[str, Any]
    request_tools: List[Dict[str, Any]]
    raw_output: str
    taxonomy: List[str]
    gold: Dict[str, Any]
    note: Optional[str] = None
    path: Optional[str] = field(default=None, compare=False)


def _cases_dir(corpus_dir: str) -> Path:
    base = Path(corpus_dir)
    cases = base / "cases"
    return cases if cases.is_dir() else base


def load_cases(corpus_dir: str) -> List[Case]:
    """Load every case JSON under ``corpus_dir`` (or its ``cases/`` subdir).

    Returns cases sorted by filename. Files that fail to parse or lack required
    fields are skipped and logged to stderr.
    """
    cases_dir = _cases_dir(corpus_dir)
    cases: List[Case] = []

    if not cases_dir.is_dir():
        print(f"[tcrb.case] no cases directory at {cases_dir}", file=sys.stderr)
        return cases

    files = sorted(cases_dir.glob("*.json"), key=lambda p: p.name)
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
            case = Case(
                id=data["id"],
                provenance=data["provenance"],
                request_tools=data["request_tools"],
                raw_output=data["raw_output"],
                taxonomy=data["taxonomy"],
                gold=data["gold"],
                note=data.get("note"),
                path=str(path),
            )
        except (ValueError, KeyError, TypeError) as exc:
            print(
                f"[tcrb.case] SKIP {path.name}: failed to parse ({exc})",
                file=sys.stderr,
            )
            continue
        cases.append(case)

    print(
        f"[tcrb.case] loaded {len(cases)} case(s) from {cases_dir}",
        file=sys.stderr,
    )
    return cases


def tool_names(case: Case) -> List[str]:
    """Return the offered tool names for ``case``."""
    return [t["name"] for t in case.request_tools]
