from __future__ import annotations

import csv
import json
from dataclasses import asdict, replace
from pathlib import Path

from draftcode.dossier import load_team_dossiers
from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.official import MOCK_SIGNALS_COLUMNS, TEAM_NEEDS_COLUMNS, ingest_official
from draftcode.preference import preference_score
from draftcode.simulate import MonteCarloDraftTwin, SimulationConfig

DOSSIER_PATH = Path("data/dossiers/team_dossiers.json")
SAMPLE_DIR = Path("data/sample")
SOURCE_DIR = Path("data/raw/official")


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def test_preference_weights_change_with_persona() -> None:
    dossiers = load_team_dossiers(DOSSIER_PATH)
    prospect = load_prospects(SAMPLE_DIR)[0]
    bpa = dossiers["WAS"]
    need = replace(
        dossiers["MIL"],
        roster_needs={"G": 0.10, "W": 0.95, "B": 0.10},
    )
    components = {
        "board_score": 0.88,
        "production_score": 0.64,
        "need_score": 0.95,
        "mock_score": 0.25,
    }

    bpa_score, bpa_breakdown = preference_score(bpa, prospect, components)
    need_score, need_breakdown = preference_score(need, prospect, components)

    assert bpa_breakdown["philosophy"] == "BPA"
    assert need_breakdown["philosophy"] == "NEED"
    assert bpa_breakdown["w_talent"] > need_breakdown["w_talent"]
    assert need_breakdown["w_need"] > bpa_breakdown["w_need"]
    assert bpa_score != need_score


def test_ingest_generates_nonempty_team_needs_and_mock_signals(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    report = ingest_official(SOURCE_DIR, out_dir)

    need_columns, need_rows = _read_csv(out_dir / "team_needs.csv")
    signal_columns, signal_rows = _read_csv(out_dir / "mock_signals.csv")
    _, draft_rows = _read_csv(out_dir / "draft_order.csv")
    draft_abbreviations = {row["abbreviation"] for row in draft_rows}

    assert report["dossier_count"] == 30
    assert need_columns == TEAM_NEEDS_COLUMNS
    assert signal_columns == MOCK_SIGNALS_COLUMNS
    assert need_rows
    assert signal_rows
    assert {
        row["abbreviation"] for row in need_rows
    } == draft_abbreviations
    assert all(row["position"] in {"G", "W", "B"} for row in need_rows)
    assert all(0 <= float(row["weight"]) <= 1 for row in need_rows)
    assert all(0 <= float(row["signal_strength"]) <= 1 for row in signal_rows)
    assert all(row["source"] == "handbook-market" for row in signal_rows)


def test_monte_carlo_with_dossiers_is_deterministic_and_traced() -> None:
    dossiers = load_team_dossiers(DOSSIER_PATH)
    config = SimulationConfig(draws=60, seed=123)
    first_twin = MonteCarloDraftTwin(
        prospects=load_prospects(SAMPLE_DIR),
        draft_order=load_draft_order(SAMPLE_DIR),
        team_needs=load_team_needs(SAMPLE_DIR),
        mock_signals=load_mock_signals(SAMPLE_DIR),
        config=config,
        dossiers=dossiers,
    )
    second_twin = MonteCarloDraftTwin(
        prospects=load_prospects(SAMPLE_DIR),
        draft_order=load_draft_order(SAMPLE_DIR),
        team_needs=load_team_needs(SAMPLE_DIR),
        mock_signals=load_mock_signals(SAMPLE_DIR),
        config=config,
        dossiers=dossiers,
    )

    first = first_twin.run()
    second = second_twin.run()

    assert asdict(first) == asdict(second)
    assert first_twin.preference_trace
    first_candidate = first_twin.preference_trace[0]["top_candidates"][0]
    assert first_candidate["preference"]["philosophy"]
    for pick in first.picks:
        assert 0 <= pick.probability <= 1
        assert all(0 <= candidate.probability <= 1 for candidate in pick.distribution)


def test_without_dossiers_matches_existing_run_byte_for_byte() -> None:
    config = SimulationConfig(draws=60, seed=321)
    args = {
        "prospects": load_prospects(SAMPLE_DIR),
        "draft_order": load_draft_order(SAMPLE_DIR),
        "team_needs": load_team_needs(SAMPLE_DIR),
        "mock_signals": load_mock_signals(SAMPLE_DIR),
        "config": config,
    }

    baseline = MonteCarloDraftTwin(**args).run()
    explicit_none = MonteCarloDraftTwin(**args, dossiers=None).run()

    baseline_json = json.dumps(asdict(baseline), sort_keys=True, ensure_ascii=True)
    explicit_json = json.dumps(asdict(explicit_none), sort_keys=True, ensure_ascii=True)
    assert baseline_json == explicit_json
