"""Schema validation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "corpus"
SCHEMA_PATH = CORPUS_DIR / "schema" / "case.schema.json"
CASES_DIR = CORPUS_DIR / "cases"


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _case_files():
    return sorted(CASES_DIR.glob("*.json"), key=lambda p: p.name)


def test_schema_exists():
    assert SCHEMA_PATH.is_file(), f"missing schema at {SCHEMA_PATH}"


@pytest.mark.parametrize("path", _case_files(), ids=lambda p: p.name)
def test_every_case_validates(path):
    validator = Draft202012Validator(_schema())
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = list(validator.iter_errors(data))
    assert not errors, f"{path.name} failed: {[e.message for e in errors]}"


def test_malformed_case_fails_validation():
    validator = Draft202012Validator(_schema())
    bad = {
        "id": "BAD ID with spaces",  # violates kebab-case pattern
        "provenance": {"model": "x"},  # missing required "source"
        "request_tools": "not-an-array",
        "raw_output": 123,  # wrong type
        "taxonomy": ["not_a_real_label"],  # not in enum
        "gold": {"type": "tool_call"},  # missing name/arguments
    }
    errors = list(validator.iter_errors(bad))
    assert errors, "deliberately malformed case unexpectedly validated"
