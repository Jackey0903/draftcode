from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from typer.testing import CliRunner

from draftcode.cli import app
from draftcode.dossier import load_team_dossiers
from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.simulate import MonteCarloDraftTwin, SimulationConfig

SAMPLE_DIR = Path("data/sample")
DOSSIER_PATH = Path("data/dossiers/team_dossiers.json")


def test_gm_preferences_raise_team_pick_probability() -> None:
    config = SimulationConfig(draws=600, seed=77)
    args = _sample_args(config)
    target_prospect_id = "p004"

    baseline = MonteCarloDraftTwin(**args).run()
    influenced_twin = MonteCarloDraftTwin(
        **args,
        gm_preferences={"ATL": {target_prospect_id: 0.08}},
    )
    influenced = influenced_twin.run()

    assert _pick_probability(influenced, 1, target_prospect_id) > _pick_probability(
        baseline,
        1,
        target_prospect_id,
    )

    trace_candidate = next(
        row
        for row in influenced_twin.preference_trace[0]["top_candidates"]
        if row["prospect_id"] == target_prospect_id
    )
    preference = trace_candidate["preference"]
    assert preference["llm_raw_delta"] == 0.08
    assert preference["llm_weight"] == 0.5
    assert preference["llm_delta"] == 0.04


def test_missing_gm_preferences_matches_existing_run_byte_for_byte() -> None:
    config = SimulationConfig(draws=80, seed=321)
    args = _sample_args(config)

    baseline = MonteCarloDraftTwin(**args).run()
    empty_preferences = MonteCarloDraftTwin(**args, gm_preferences={}).run()

    baseline_json = json.dumps(asdict(baseline), sort_keys=True, ensure_ascii=True)
    empty_json = json.dumps(asdict(empty_preferences), sort_keys=True, ensure_ascii=True)
    assert baseline_json == empty_json


def test_cli_simulate_degrades_for_missing_or_bad_gm_preferences(tmp_path: Path) -> None:
    runner = CliRunner()
    bad_preferences = tmp_path / "bad_gm_preferences.json"
    bad_preferences.write_text("{bad json", encoding="utf-8")
    bad_output = tmp_path / "bad_twin.json"
    missing_output = tmp_path / "missing_twin.json"

    bad_result = runner.invoke(
        app,
        [
            "simulate",
            "--data-dir",
            str(SAMPLE_DIR),
            "--output",
            str(bad_output),
            "--draws",
            "20",
            "--seed",
            "9",
            "--gm-preferences",
            str(bad_preferences),
        ],
    )
    missing_result = runner.invoke(
        app,
        [
            "simulate",
            "--data-dir",
            str(SAMPLE_DIR),
            "--output",
            str(missing_output),
            "--draws",
            "20",
            "--seed",
            "9",
            "--gm-preferences",
            str(tmp_path / "missing_gm_preferences.json"),
        ],
    )

    assert bad_result.exit_code == 0, bad_result.output
    assert missing_result.exit_code == 0, missing_result.output
    assert "GM preferences disabled" in bad_result.output
    assert "GM preferences disabled" in missing_result.output
    assert bad_output.read_text(encoding="utf-8") == missing_output.read_text(encoding="utf-8")


def _sample_args(config: SimulationConfig) -> dict[str, object]:
    return {
        "prospects": load_prospects(SAMPLE_DIR),
        "draft_order": load_draft_order(SAMPLE_DIR),
        "team_needs": load_team_needs(SAMPLE_DIR),
        "mock_signals": load_mock_signals(SAMPLE_DIR),
        "config": config,
        "dossiers": load_team_dossiers(DOSSIER_PATH),
    }


def _pick_probability(report: object, pick_number: int, prospect_id: str) -> float:
    pick = next(row for row in report.picks if row.pick == pick_number)
    return next(
        (
            candidate.probability
            for candidate in pick.distribution
            if candidate.prospect_id == prospect_id
        ),
        0.0,
    )
