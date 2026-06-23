from __future__ import annotations

import csv
from pathlib import Path

from draftcode.io import load_prospects
from draftcode.official import PROSPECT_COLUMNS, ingest_official, parse_feet_inches

SOURCE_DIR = Path("data/raw/official")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_feet_inches_parser() -> None:
    assert parse_feet_inches("6' 3.75''") == 75.75
    assert parse_feet_inches("7' 3.25''") == 87.25
    assert parse_feet_inches("") is None


def test_normalizer_outputs_engine_ready_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    report = ingest_official(SOURCE_DIR, out_dir)

    prospects = _read_csv(out_dir / "prospects.csv")
    draft_order = _read_csv(out_dir / "draft_order.csv")

    assert report["pool_count"] == 124
    assert len(prospects) == 124
    assert len(draft_order) == 30
    assert set(PROSPECT_COLUMNS) <= set(prospects[0])
    assert (out_dir / "team_needs.csv").exists()
    assert (out_dir / "mock_signals.csv").exists()
    assert (out_dir / "q6_options.json").exists()
    assert (out_dir / "divergence.json").exists()
    assert (out_dir / "ingest_report.json").exists()
    assert report["market_coverage"]["market_rank_count"] >= 18
    assert report["divergence_stats"]["market_fade"] >= 3


def test_key_anchors(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    ingest_official(SOURCE_DIR, out_dir)
    rows = _read_csv(out_dir / "prospects.csv")
    by_id = {row["prospect_id"]: row for row in rows}

    assert by_id["p001"]["name"] == "AJ 迪班萨"
    assert int(by_id["p001"]["consensus_rank"]) == 1
    assert by_id["p001"]["board_source"] == "handbook"
    assert by_id["p023"]["divergence_type"] == "market_fade"
    assert by_id["p011"]["divergence_type"] == "market_fade"
    assert by_id["p023"]["divergence_reason"]
    assert by_id["p011"]["divergence_reason"]
    assert by_id["p001"]["market_rank"] == "1"
    assert by_id["p001"]["talent_rank"] == "2"
    assert sum(row["is_center"] == "true" for row in rows) == 14
    assert sum(row["is_international"] == "true" for row in rows) >= 11


def test_engine_can_load_official_prospects(tmp_path: Path) -> None:
    out_dir = tmp_path / "processed"
    ingest_official(SOURCE_DIR, out_dir)

    prospects = load_prospects(out_dir)

    assert len(prospects) == 124
    assert prospects[0].prospect_id == "p001"


def test_normalizer_is_deterministic(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    ingest_official(SOURCE_DIR, first_dir)
    ingest_official(SOURCE_DIR, second_dir)

    assert (first_dir / "prospects.csv").read_bytes() == (
        second_dir / "prospects.csv"
    ).read_bytes()
    assert (first_dir / "divergence.json").read_bytes() == (
        second_dir / "divergence.json"
    ).read_bytes()
