from __future__ import annotations

import csv
from pathlib import Path

from draftcode.rerank import fuse_consensus_ranks

_FIELDS = [
    "prospect_id",
    "name",
    "talent_signal",
    "market_rank",
    "market_signal",
    "odds_signal",
    "consensus_rank",
    "fused_score",
]


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in _FIELDS})


def _read(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["prospect_id"]: row for row in csv.DictReader(handle)}


def test_market_darling_outranks_talent_only(tmp_path: Path) -> None:
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    _write(
        data_dir / "prospects.csv",
        [
            # High talent but NO market/odds support -> should sink.
            {"prospect_id": "p1", "name": "TalentOnly", "talent_signal": "0.9"},
            # Low talent but strong market + odds -> should rise (market anchor).
            {
                "prospect_id": "p2",
                "name": "MarketDarling",
                "talent_signal": "0.2",
                "market_signal": "0.95",
                "odds_signal": "0.4",
            },
        ],
    )
    fuse_consensus_ranks(data_dir)
    rows = _read(data_dir / "prospects.csv")
    assert int(rows["p2"]["consensus_rank"]) < int(rows["p1"]["consensus_rank"])
    assert float(rows["p2"]["fused_score"]) > float(rows["p1"]["fused_score"])


def test_unmocked_player_sinks_below_mocked(tmp_path: Path) -> None:
    data_dir = tmp_path / "processed"
    data_dir.mkdir()
    _write(
        data_dir / "prospects.csv",
        [
            {"prospect_id": "p1", "name": "Mocked", "talent_signal": "0.3", "market_signal": "0.9"},
            {"prospect_id": "p2", "name": "NoMarket", "talent_signal": "0.5"},
        ],
    )
    fuse_consensus_ranks(data_dir)
    rows = _read(data_dir / "prospects.csv")
    assert int(rows["p1"]["consensus_rank"]) < int(rows["p2"]["consensus_rank"])
