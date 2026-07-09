"""Capture scaffold tests — deterministic, no network, no auto-labeling."""

from __future__ import annotations

import json

from tcrb.capture import build_pending_case, main


def test_pending_case_is_not_auto_labeled():
    case = build_pending_case(
        "0042-qwen-fenced",
        raw_output='```json\n{"name": "search"}\n```',
        model="qwen2.5-coder:7b",
        runtime="ollama",
        harness="opencode",
    )
    # The scaffold must never guess: taxonomy empty, gold unset, marked pending.
    assert case["_pending"] is True
    assert case["taxonomy"] == []
    assert case["gold"] is None
    assert case["provenance"]["kind"] == "captured"
    assert case["provenance"]["model"] == "qwen2.5-coder:7b"
    assert case["provenance"]["runtime"] == "ollama"
    assert case["raw_output"].startswith("```json")


def test_pending_case_is_deterministic():
    a = build_pending_case("x", "raw", "m", runtime="ollama")
    b = build_pending_case("x", "raw", "m", runtime="ollama")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_main_writes_pending_file_from_stdin(tmp_path, monkeypatch, capsys):
    raw_file = tmp_path / "out.txt"
    raw_file.write_text("plain answer, no call", encoding="utf-8")
    out_dir = tmp_path / "pending"

    rc = main(
        [
            "--id", "0099-sample",
            "--raw", str(raw_file),
            "--model", "gemma4:e4b-mlx",
            "--runtime", "ollama",
            "--out", str(out_dir),
        ]
    )
    assert rc == 0
    written = out_dir / "0099-sample.json"
    assert written.is_file()
    data = json.loads(written.read_text(encoding="utf-8"))
    assert data["_pending"] is True
    assert data["gold"] is None
    assert data["raw_output"] == "plain answer, no call"


def test_pending_case_omits_unset_optional_fields():
    case = build_pending_case("x", "raw", "m")
    prov = case["provenance"]
    assert "runtime" not in prov
    assert "harness" not in prov
    assert "temperature" not in prov
    # source always gets a default so the draft is traceable.
    assert "source" in prov
