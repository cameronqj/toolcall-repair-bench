"""Schema validation gate.

Validates every case file under ``corpus/cases/`` against
``corpus/schema/case.schema.json`` using ``jsonschema``. Prints one line per
case (ok / FAIL) in filename-sorted order and exits nonzero if any case is
invalid. Runs in CI.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator

DEFAULT_CORPUS_DIR = "corpus"


def _load_schema(corpus_dir: str) -> Dict[str, Any]:
    schema_path = Path(corpus_dir) / "schema" / "case.schema.json"
    with schema_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def check_integrity(cases: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
    """Cross-case invariants the JSON Schema cannot express on its own.

    ``cases`` is a list of ``(filename, data)`` for files that parsed and
    passed per-file schema validation. Returns a sorted list of human-readable
    error strings; empty means the corpus is internally consistent.
    """
    errors: List[str] = []

    # 1. Unique case ids (and id should match the filename stem).
    seen: Dict[str, str] = {}
    for name, data in cases:
        cid = data.get("id")
        if cid in seen:
            errors.append(
                f"duplicate id {cid!r}: in both {seen[cid]} and {name}"
            )
        else:
            seen[cid] = name
        stem = name[:-5] if name.endswith(".json") else name
        if cid != stem:
            errors.append(f"{name}: id {cid!r} does not match filename stem {stem!r}")

    # 2. A gold tool_call must name a tool that was actually offered.
    for name, data in cases:
        gold = data.get("gold", {})
        if gold.get("type") == "tool_call":
            offered = {t.get("name") for t in data.get("request_tools", [])}
            if gold.get("name") not in offered:
                errors.append(
                    f"{name}: gold tool_call name {gold.get('name')!r} is not in "
                    f"request_tools {sorted(n for n in offered if n)}"
                )

    # 3. Provenance must be explicit and self-consistent.
    #    - kind is captured or synthetic (the schema enforces the enum; here we
    #      enforce cross-field agreement the schema cannot express);
    #    - the legacy `synthetic` boolean, if present, must agree with kind;
    #    - a captured case must name a real model (not "synthetic");
    #    - a synthetic case must be labeled synthetic via model == "synthetic".
    for name, data in cases:
        prov = data.get("provenance", {})
        kind = prov.get("kind")
        model = prov.get("model")
        synthetic_flag = prov.get("synthetic")

        if kind not in ("captured", "synthetic"):
            errors.append(
                f"{name}: provenance.kind must be 'captured' or 'synthetic', "
                f"got {kind!r}"
            )
            continue

        if synthetic_flag is not None and synthetic_flag != (kind == "synthetic"):
            errors.append(
                f"{name}: provenance.synthetic ({synthetic_flag!r}) disagrees with "
                f"kind ({kind!r})"
            )

        if kind == "captured":
            if model == "synthetic":
                errors.append(
                    f"{name}: captured case must name a real model, not 'synthetic'"
                )
            if not model:
                errors.append(f"{name}: captured case must record provenance.model")
        else:  # synthetic
            if model != "synthetic":
                errors.append(
                    f"{name}: synthetic case must set provenance.model to "
                    f"'synthetic', got {model!r}"
                )

    return sorted(errors)


def validate_corpus(corpus_dir: str = DEFAULT_CORPUS_DIR) -> int:
    """Validate every case file. Return the number of problems found.

    Prints one ``ok``/``FAIL`` line per case, then runs cross-case integrity
    checks (unique ids, gold names that were actually offered). A return value
    of 0 means the whole corpus validates and is internally consistent.
    """
    base = Path(corpus_dir)
    schema_path = base / "schema" / "case.schema.json"
    cases_dir = base / "cases"

    if not schema_path.is_file():
        print(f"FAIL: schema not found at {schema_path}", file=sys.stderr)
        return 1

    schema = _load_schema(corpus_dir)
    validator = Draft202012Validator(schema)

    if not cases_dir.is_dir():
        print(f"FAIL: cases directory not found at {cases_dir}", file=sys.stderr)
        return 1

    files = sorted(cases_dir.glob("*.json"), key=lambda p: p.name)
    if not files:
        print(f"WARNING: no case files found in {cases_dir}", file=sys.stderr)
        return 0

    invalid = 0
    valid_cases: List[Tuple[str, Dict[str, Any]]] = []
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except ValueError as exc:
            print(f"FAIL {path.name}: not valid JSON ({exc})")
            invalid += 1
            continue

        errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
        if errors:
            invalid += 1
            print(f"FAIL {path.name}:")
            for err in errors:
                location = "/".join(str(p) for p in err.path) or "<root>"
                print(f"    {location}: {err.message}")
        else:
            print(f"ok   {path.name}")
            valid_cases.append((path.name, data))

    print(f"{len(files) - invalid}/{len(files)} case(s) valid")

    integrity_errors = check_integrity(valid_cases)
    if integrity_errors:
        print(f"FAIL: {len(integrity_errors)} corpus integrity problem(s):")
        for err in integrity_errors:
            print(f"    {err}")
    else:
        print("corpus integrity: ok")

    return invalid + len(integrity_errors)


def main() -> int:
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CORPUS_DIR
    invalid = validate_corpus(corpus_dir)
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
