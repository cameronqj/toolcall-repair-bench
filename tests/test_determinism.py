"""Determinism tests: byte-identical output across runs."""

from __future__ import annotations

import json
from pathlib import Path

from tcrb.leaderboard import render_markdown
from tcrb.scorer import score

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = str(REPO_ROOT / "corpus")


def test_score_is_byte_identical():
    a = json.dumps(score(CORPUS_DIR), sort_keys=True)
    b = json.dumps(score(CORPUS_DIR), sort_keys=True)
    assert a == b


def test_render_markdown_is_stable():
    results = score(CORPUS_DIR)
    assert render_markdown(results) == render_markdown(results)
