from __future__ import annotations

import csv
import json
from pathlib import Path

from draftcode import llm_client
from draftcode.intel import IntelReport, NeedsDelta, PickMove, apply_intel, extract_intel
from draftcode.io import load_draft_order

GIANNIS_INTEL_JSON = {
    "picks_moved_2026_round1": [
        {
            "pick_number": 13,
            "from_team": "Miami Heat",
            "to_team": "Milwaukee Bucks",
        }
    ],
    "team_needs_delta": [
        {
            "team": "Milwaukee Bucks",
            "new_timeline": "retool",
            "position_focus": "forward upside",
        },
        {
            "team": "Miami Heat",
            "new_timeline": "win-now",
            "position_focus": "cheap guard/wing",
        },
    ],
    "affects_our_draft_order": True,
}


def test_extract_intel_parses_giannis_pick_move(tmp_path: Path, monkeypatch) -> None:
    data_dir = _write_processed_inputs(tmp_path / "processed")
    draft_order = load_draft_order(data_dir)

    monkeypatch.setattr(
        llm_client,
        "complete",
        lambda prompt, schema=None, timeout=180: json.dumps(GIANNIS_INTEL_JSON),
    )

    report = extract_intel(
        "Giannis Antetokounmpo is traded to Miami; Milwaukee receives pick 13.",
        draft_order,
        source="test-news",
    )

    assert report.affects_draft_order is True
    assert report.picks_moved == [PickMove(13, "MIA", "MIL")]
    assert report.needs_delta[0] == NeedsDelta("MIL", "retool", "forward upside")


def test_apply_intel_dry_run_previews_without_writing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = _write_processed_inputs(tmp_path / "processed")
    report = _sample_report()

    result = apply_intel(report, data_dir, dry_run=True)

    rows = _read_csv(data_dir / "draft_order.csv")
    pick_13 = next(row for row in rows if row["pick"] == "13")
    assert pick_13["abbreviation"] == "MIA"
    assert result["draft_order_changes"][0]["from"] == "MIA"
    assert result["draft_order_changes"][0]["to"] == "MIL"
    assert Path(result["audit_path"]).exists()


def test_apply_intel_updates_draft_order_and_needs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = _write_processed_inputs(tmp_path / "processed")
    report = _sample_report()

    result = apply_intel(report, data_dir, dry_run=False)

    rows = _read_csv(data_dir / "draft_order.csv")
    pick_13 = next(row for row in rows if row["pick"] == "13")
    assert pick_13["team"] == "Milwaukee Bucks"
    assert pick_13["abbreviation"] == "MIL"
    assert pick_13["via_trade"] == "true"
    assert pick_13["original_team"] == "MIA"

    needs = _read_csv(data_dir / "team_needs.csv")
    mil_wing = next(row for row in needs if row["abbreviation"] == "MIL" and row["position"] == "W")
    assert mil_wing["weight"] == "0.85"
    assert mil_wing["timeline"] == "retool"
    assert Path(result["audit_path"]).exists()


def test_apply_intel_writes_audit_trace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = _write_processed_inputs(tmp_path / "processed")

    result = apply_intel(_sample_report(), data_dir, dry_run=True)

    audit = json.loads(Path(result["audit_path"]).read_text(encoding="utf-8"))
    assert audit["report"]["raw_excerpt"] == "Heat acquire Giannis from Bucks."
    assert audit["application"]["draft_order_changes"][0]["new_abbreviation"] == "MIL"
    assert list((tmp_path / "outputs" / "intel").glob("intel_*.json"))


def test_extract_intel_llm_fallback_returns_empty_report(tmp_path: Path, monkeypatch) -> None:
    data_dir = _write_processed_inputs(tmp_path / "processed")
    draft_order = load_draft_order(data_dir)
    monkeypatch.setattr(llm_client, "complete", lambda prompt, schema=None, timeout=180: None)

    report = extract_intel("Heat acquire Giannis from Bucks.", draft_order)

    assert report.picks_moved == []
    assert report.needs_delta == []
    assert report.affects_draft_order is False


def _sample_report() -> IntelReport:
    return IntelReport(
        picks_moved=[PickMove(13, "MIA", "MIL")],
        needs_delta=[NeedsDelta("MIL", "retool", "forward upside")],
        affects_draft_order=True,
        raw_excerpt="Heat acquire Giannis from Bucks.",
        source="test-news",
    )


def _write_processed_inputs(data_dir: Path) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(
        data_dir / "draft_order.csv",
        ["pick", "team", "abbreviation"],
        [
            {"pick": "10", "team": "Milwaukee Bucks", "abbreviation": "MIL"},
            {"pick": "13", "team": "Miami Heat", "abbreviation": "MIA"},
        ],
    )
    _write_csv(
        data_dir / "team_needs.csv",
        ["abbreviation", "position", "weight"],
        [
            {"abbreviation": "MIL", "position": "G", "weight": "0.74"},
            {"abbreviation": "MIL", "position": "W", "weight": "0.66"},
            {"abbreviation": "MIL", "position": "B", "weight": "0.52"},
            {"abbreviation": "MIA", "position": "G", "weight": "0.66"},
            {"abbreviation": "MIA", "position": "W", "weight": "0.76"},
            {"abbreviation": "MIA", "position": "B", "weight": "0.54"},
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
