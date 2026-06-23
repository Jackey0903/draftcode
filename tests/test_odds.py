from __future__ import annotations

import csv
import json
from pathlib import Path

from draftcode import llm_client
from draftcode import odds as odds_mod
from draftcode.odds import (
    ConsensusOdds,
    OddsReport,
    aggregate_odds,
    american_to_implied,
    apply_odds,
    devig,
)

ESPN_ODDS = {
    "markets": [
        {
            "pick": 1,
            "entries": [
                {
                    "raw_player_name": "AJ Dybantsa",
                    "matched_prospect_name": "AJ 迪班萨",
                    "american_odds": -550,
                },
                {
                    "raw_player_name": "Darryn Peterson",
                    "matched_prospect_name": "达林 彼得森",
                    "american_odds": 475,
                },
            ],
        }
    ]
}

OS_ODDS = {
    "markets": [
        {
            "pick": 1,
            "entries": [
                {
                    "raw_player_name": "AJ Dybantsa",
                    "matched_prospect_name": "AJ 迪班萨",
                    "american_odds": -750,
                },
                {
                    "raw_player_name": "Darryn Peterson",
                    "matched_prospect_name": "达林 彼得森",
                    "american_odds": 600,
                },
            ],
        }
    ]
}


def test_american_to_implied_and_devig() -> None:
    assert abs(american_to_implied(-550) - 550 / 650) < 1e-9
    assert abs(american_to_implied(475) - 100 / 575) < 1e-9
    assert abs(american_to_implied(-225) - 225 / 325) < 1e-9
    assert abs(american_to_implied(100) - 0.5) < 1e-9

    devigged = devig([0.8462, 0.1739])
    assert abs(sum(devigged) - 1.0) < 1e-9
    assert devig([0.0, 0.0]) == [0.0, 0.0]


def test_aggregate_odds_cross_source_consensus(monkeypatch) -> None:
    monkeypatch.setattr(llm_client, "complete", _fake_odds_complete)

    report = aggregate_odds(
        [("ESPN", "odds text"), ("OS", "odds text")],
        ["AJ 迪班萨", "达林 彼得森"],
    )

    distribution = report.per_pick_distribution[1]
    assert abs(sum(prob for _, prob in distribution) - 1.0) < 1e-9

    by_name = {ranking.prospect_name: ranking for ranking in report.rankings}
    dybantsa = by_name["AJ 迪班萨"]
    assert dybantsa.odds_rank == 1
    assert dybantsa.n_sources == 2
    assert 0.80 < dybantsa.odds_signal < 0.88  # de-vigged consensus favorite
    assert by_name["达林 彼得森"].odds_signal < dybantsa.odds_signal
    assert report.source_names == ["ESPN", "OS"]


def test_apply_odds_writes_signals_and_audit(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_client, "complete", _fake_odds_complete)
    data_dir = _write_inputs(tmp_path / "processed")

    report = aggregate_odds(
        [("ESPN", "odds text"), ("OS", "odds text")],
        ["AJ 迪班萨", "达林 彼得森"],
    )
    result = apply_odds(report, data_dir, dry_run=False)

    by_id = {row["prospect_id"]: row for row in _read_csv(data_dir / "prospects.csv")}
    assert by_id["p001"]["odds_signal"]  # non-empty for the favorite
    assert by_id["p001"]["odds_rank"] == "1"
    assert result["odds_coverage_after"] >= 1
    assert result["wrote_csv"] is True

    signals = _read_csv(data_dir / "odds_signals.csv")
    assert signals
    assert {row["source"] for row in signals} == {"consensus"}
    assert any(
        row["abbreviation"] == "WAS" and row["prospect_id"] == "p001" for row in signals
    )

    audit_path = Path(result["audit_path"])
    assert audit_path.exists()
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["consensus"][0]["prospect_name"] == "AJ 迪班萨"
    assert "1" in audit["per_pick_distribution"]


def test_apply_odds_dry_run_writes_nothing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_client, "complete", _fake_odds_complete)
    data_dir = _write_inputs(tmp_path / "processed")

    report = aggregate_odds([("ESPN", "odds text")], ["AJ 迪班萨", "达林 彼得森"])
    result = apply_odds(report, data_dir, dry_run=True)

    assert result["wrote_csv"] is False
    assert not (data_dir / "odds_signals.csv").exists()
    by_id = {row["prospect_id"]: row for row in _read_csv(data_dir / "prospects.csv")}
    assert by_id["p001"].get("odds_signal", "") == ""
    assert Path(result["audit_path"]).exists()


def test_aggregate_odds_llm_fallback_empty(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(llm_client, "complete", lambda prompt, schema=None, timeout=180: None)
    data_dir = _write_inputs(tmp_path / "processed")

    report = aggregate_odds([("ESPN", "odds text")], ["AJ 迪班萨"])
    result = apply_odds(report, data_dir, dry_run=False)

    assert report.rankings == []
    assert report.source_names == []
    assert result["wrote_csv"] is False
    assert not (data_dir / "odds_signals.csv").exists()
    assert Path(result["audit_path"]).exists()


def test_axis2_divergence_rule_and_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        odds_mod,
        "reason_odds_divergence",
        lambda **kwargs: {"verdict": "odds_sharp", "confidence": 0.7, "reasoning": "money leads"},
    )
    report = OddsReport(
        rankings=[
            ConsensusOdds(
                prospect_name="达林 彼得森",
                odds_rank=2,
                odds_signal=0.9,
                n_sources=1,
                sources=["ESPN"],
            )
        ],
        source_names=["ESPN"],
        per_pick_distribution={2: [("达林 彼得森", 0.9)]},
    )
    prospect_rows = [
        {"prospect_id": "p051", "name": "达林 彼得森", "market_rank": "15", "primary_position": "G"}
    ]
    cache: dict = {}
    records = odds_mod._build_axis2_records(report, prospect_rows, use_llm=True, cache=cache)

    record = records["p051"]
    assert record["divergence_gap_axis2"] == 13  # mock 15 vs odds 2
    assert record["divergence_type_axis2"] == "odds_sharp"
    assert record["divergence_odds_llm_verdict"] == "odds_sharp"
    assert cache["p051"]["verdict"] == "odds_sharp"  # cached for determinism

    # Rule-only boundaries.
    assert odds_mod._axis2_type(3) == "aligned"
    assert odds_mod._axis2_type(-12) == "mock_sharp"


def _fake_odds_complete(prompt: str, schema=None, timeout: int = 180) -> str:
    if "Source: ESPN" in prompt:
        return json.dumps(ESPN_ODDS, ensure_ascii=False)
    if "Source: OS" in prompt:
        return json.dumps(OS_ODDS, ensure_ascii=False)
    return json.dumps({"markets": []})


def _write_inputs(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        data_dir / "prospects.csv",
        ["prospect_id", "name"],
        [
            {"prospect_id": "p001", "name": "AJ 迪班萨"},
            {"prospect_id": "p051", "name": "达林 彼得森"},
        ],
    )
    _write_csv(
        data_dir / "draft_order.csv",
        ["pick", "team", "abbreviation"],
        [
            {"pick": "1", "team": "Washington Wizards", "abbreviation": "WAS"},
            {"pick": "2", "team": "Utah Jazz", "abbreviation": "UTA"},
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
