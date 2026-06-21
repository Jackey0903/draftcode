from __future__ import annotations

from pathlib import Path

from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.model import DraftPredictor
from draftcode.pipeline import run_prediction


SAMPLE_DIR = Path("data/sample")


def test_prediction_outputs_one_unique_prospect_per_pick() -> None:
    picks = run_prediction(SAMPLE_DIR)

    assert len(picks) == len(load_draft_order(SAMPLE_DIR))
    assert len({pick.prospect_id for pick in picks}) == len(picks)
    assert all(0 <= pick.confidence <= 1 for pick in picks)


def test_mock_signal_can_move_a_close_decision() -> None:
    prospects = load_prospects(SAMPLE_DIR)
    draft_order = load_draft_order(SAMPLE_DIR)[:1]
    team_needs = load_team_needs(SAMPLE_DIR)
    mock_signals = load_mock_signals(SAMPLE_DIR)

    picks, trace = DraftPredictor().predict(prospects, draft_order, team_needs, mock_signals)

    assert picks[0].abbreviation == "ATL"
    assert picks[0].prospect_id
    assert trace["picks"][0]["top_candidates"]
