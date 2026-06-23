from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from draftcode.cli import app
from draftcode.warroom import load_gm_adjustments

SAMPLE_DIR = Path("data/sample")


def test_warroom_offline_cli_writes_fallback_artifacts(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "warroom",
            "--data-dir",
            str(SAMPLE_DIR),
            "--output-dir",
            str(tmp_path),
            "--draws",
            "20",
            "--seed",
            "11",
            "--offline",
        ],
    )

    assert result.exit_code == 0, result.output

    gm_preferences = _read_json(tmp_path / "gm_preferences.json")
    explanations = _read_json(tmp_path / "explanations.json")
    redteam = _read_json(tmp_path / "redteam.json")

    assert gm_preferences["schema_version"] == 1
    assert gm_preferences["mode"] == "offline"
    assert len(gm_preferences["teams"]) == 30
    assert all(not row["used_llm"] for row in gm_preferences["teams"].values())
    assert all(row["adjustments"] == {} for row in gm_preferences["teams"].values())

    assert explanations["schema_version"] == 1
    assert explanations["mode"] == "offline"
    assert len(explanations["picks"]) == 10
    assert all(not row["used_llm"] for row in explanations["picks"])
    assert all(row["text"] for row in explanations["picks"])

    assert redteam["schema_version"] == 1
    assert redteam["mode"] == "offline"
    assert redteam["used_llm"] is False
    assert redteam["questions"]


def test_load_gm_adjustments_reads_cache_shape(tmp_path: Path) -> None:
    cache = {
        "schema_version": 1,
        "mode": "llm-once",
        "teams": {
            "UTA": {
                "used_llm": True,
                "adjustments": {"p001": 0.11, "p002": "-0.03", "bad": "x"},
            }
        },
    }
    path = tmp_path / "gm_preferences.json"
    path.write_text(json.dumps(cache), encoding="utf-8")

    assert load_gm_adjustments(path) == {"UTA": {"p001": 0.08, "p002": -0.03}}


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
