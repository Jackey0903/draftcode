from __future__ import annotations

import csv
import json
from pathlib import Path

from draftcode import llm_client
from draftcode.market import aggregate_mocks, apply_market

ESPN_JSON = {
    "rankings": [
        {
            "raw_player_name": "AJ Dybantsa",
            "matched_prospect_name": "AJ 迪班萨",
            "projected_pick": 1,
        },
        {
            "raw_player_name": "Cameron Boozer",
            "matched_prospect_name": "卡梅隆 布泽尔",
            "projected_pick": 3,
        },
    ]
}

CBS_JSON = {
    "rankings": [
        {
            "raw_player_name": "AJ Dybantsa",
            "matched_prospect_name": "AJ 迪班萨",
            "projected_pick": 2,
        },
        {
            "raw_player_name": "Darryn Peterson",
            "matched_prospect_name": "达林 彼得森",
            "projected_pick": 5,
        },
    ]
}


def test_aggregate_mocks_averages_multisource_consensus(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "complete", _fake_market_complete)

    report = aggregate_mocks(
        [
            ("ESPN", "1. AJ Dybantsa"),
            ("CBS", "2. AJ Dybantsa"),
        ],
        ["AJ 迪班萨", "卡梅隆 布泽尔", "达林 彼得森"],
    )

    by_name = {ranking.prospect_name: ranking for ranking in report.rankings}
    assert by_name["AJ 迪班萨"].consensus_pick == 1.5
    assert by_name["AJ 迪班萨"].n_sources == 2
    assert by_name["AJ 迪班萨"].sources == ["ESPN", "CBS"]
    assert by_name["卡梅隆 布泽尔"].consensus_pick == 3
    assert report.source_names == ["ESPN", "CBS"]


def test_apply_market_updates_coverage_rewrites_signals_and_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_client, "complete", _fake_market_complete)
    data_dir = _write_market_inputs(tmp_path / "processed")
    report = aggregate_mocks(
        [
            ("ESPN", "mock text"),
            ("CBS", "mock text"),
        ],
        ["AJ 迪班萨", "卡梅隆 布泽尔", "达林 彼得森"],
    )

    result = apply_market(report, data_dir, dry_run=False)

    prospects = _read_csv(data_dir / "prospects.csv")
    by_id = {row["prospect_id"]: row for row in prospects}
    assert result["market_rank_coverage_before"] == 1
    assert result["market_rank_coverage_after"] == 3
    assert by_id["p001"]["market_rank"] == "1.5"
    assert by_id["p015"]["market_rank"] == "3"
    assert by_id["p051"]["market_rank"] == "5"

    signals = _read_csv(data_dir / "mock_signals.csv")
    assert signals
    assert {row["source"] for row in signals} == {"ESPN", "CBS"}
    assert all(row["source"] != "handbook-market" for row in signals)

    audit_path = Path(result["audit_path"])
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["source_rankings"][0]["source"] == "ESPN"
    assert audit["consensus"][0]["prospect_name"] == "AJ 迪班萨"
    assert audit["application"]["market_rank_coverage_after"] == 3


def test_aggregate_mocks_llm_fallback_returns_empty_without_writing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = _write_market_inputs(tmp_path / "processed")
    monkeypatch.setattr(llm_client, "complete", lambda prompt, schema=None, timeout=180: None)

    report = aggregate_mocks([("ESPN", "mock text")], ["AJ 迪班萨"])
    result = apply_market(report, data_dir, dry_run=False)

    assert report.rankings == []
    assert report.source_names == []
    assert result["wrote_csv"] is False
    assert _read_csv(data_dir / "mock_signals.csv") == [
        {
            "abbreviation": "WAS",
            "prospect_id": "p001",
            "signal_strength": "0.88",
            "source": "handbook-market",
        }
    ]
    assert Path(result["audit_path"]).exists()


def _fake_market_complete(prompt: str, schema=None, timeout: int = 180) -> str:
    if "Source: ESPN" in prompt:
        return json.dumps(ESPN_JSON, ensure_ascii=False)
    if "Source: CBS" in prompt:
        return json.dumps(CBS_JSON, ensure_ascii=False)
    return json.dumps({"rankings": []})


def _write_market_inputs(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        data_dir / "prospects.csv",
        ["prospect_id", "name", "market_rank"],
        [
            {"prospect_id": "p001", "name": "AJ 迪班萨", "market_rank": "1"},
            {"prospect_id": "p015", "name": "卡梅隆 布泽尔", "market_rank": ""},
            {"prospect_id": "p051", "name": "达林 彼得森", "market_rank": ""},
        ],
    )
    _write_csv(
        data_dir / "draft_order.csv",
        ["pick", "team", "abbreviation"],
        [
            {"pick": "1", "team": "Washington Wizards", "abbreviation": "WAS"},
            {"pick": "2", "team": "Utah Jazz", "abbreviation": "UTA"},
            {"pick": "3", "team": "Memphis Grizzlies", "abbreviation": "MEM"},
            {"pick": "4", "team": "Chicago Bulls", "abbreviation": "CHI"},
            {"pick": "5", "team": "Los Angeles Clippers", "abbreviation": "LAC"},
            {"pick": "6", "team": "Brooklyn Nets", "abbreviation": "BKN"},
        ],
    )
    _write_csv(
        data_dir / "mock_signals.csv",
        ["abbreviation", "prospect_id", "signal_strength", "source"],
        [
            {
                "abbreviation": "WAS",
                "prospect_id": "p001",
                "signal_strength": "0.88",
                "source": "handbook-market",
            }
        ],
    )
    return data_dir


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
