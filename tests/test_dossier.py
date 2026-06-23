from __future__ import annotations

import csv
from pathlib import Path

from draftcode.dossier import POSITIONS, load_team_dossiers
from draftcode.io import load_draft_order
from draftcode.official import ingest_official

DOSSIER_PATH = Path("data/dossiers/team_dossiers.json")
PROCESSED_DIR = Path("data/processed")
SOURCE_DIR = Path("data/raw/official")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_dossiers_cover_all_nba_teams_and_draft_order() -> None:
    dossiers = load_team_dossiers(DOSSIER_PATH)
    draft_abbreviations = {team.abbreviation for team in load_draft_order(PROCESSED_DIR)}

    assert len(dossiers) == 30
    assert draft_abbreviations <= set(dossiers)
    for abbreviation, dossier in dossiers.items():
        assert dossier.abbreviation == abbreviation
        assert set(dossier.roster_needs) == set(POSITIONS)
        assert all(0 <= weight <= 1 for weight in dossier.roster_needs.values())
        assert "初版,需赛前核实" in dossier.gm_persona.notes


def test_ingest_keeps_empty_signal_tables_without_dossier(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    missing_dossier = tmp_path / "missing-team-dossiers.json"

    ingest_official(
        SOURCE_DIR,
        out_dir,
        dossier_path=missing_dossier,
        use_llm_divergence=False,
    )

    assert _read_csv(out_dir / "team_needs.csv") == []
    assert _read_csv(out_dir / "mock_signals.csv") == []
