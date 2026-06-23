from __future__ import annotations

from pathlib import Path

from draftcode.io import (
    load_draft_order,
    load_mock_signals,
    load_prospects,
    load_team_needs,
    write_predictions,
    write_trace,
)
from draftcode.model import DraftPredictor
from draftcode.schemas import DraftPick


def run_prediction(
    data_dir: Path,
    output: Path | None = None,
    trace_path: Path | None = None,
) -> list[DraftPick]:
    prospects = load_prospects(data_dir)
    draft_order = load_draft_order(data_dir)
    team_needs = load_team_needs(data_dir)
    mock_signals = load_mock_signals(data_dir)

    picks, trace = DraftPredictor().predict(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
    )
    if output:
        write_predictions(output, picks)
    if trace_path:
        write_trace(trace_path, trace)
    return picks
