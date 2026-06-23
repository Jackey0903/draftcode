from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path
from typing import TypeVar

from draftcode.schemas import (
    DraftPick,
    MockSignal,
    OddsSignal,
    Prospect,
    Team,
    TeamNeed,
)
from draftcode.simulate import TwinReport

T = TypeVar("T")


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required data file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _optional_float(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _optional_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _optional_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() == "true"


def load_prospects(data_dir: Path) -> list[Prospect]:
    return [
        Prospect(
            prospect_id=row["prospect_id"],
            name=row["name"],
            primary_position=row["primary_position"],
            archetype=row["archetype"],
            consensus_rank=int(row["consensus_rank"]),
            age=float(row["age"]),
            height_in=float(row["height_in"]),
            wingspan_in=float(row["wingspan_in"]),
            usage_rate=float(row["usage_rate"]),
            true_shooting_pct=float(row["true_shooting_pct"]),
            assist_rate=float(row["assist_rate"]),
            rebound_rate=float(row["rebound_rate"]),
            stock_rate=float(row["stock_rate"]),
            notes=row.get("notes", ""),
            barefoot_height_in=_optional_float(row.get("barefoot_height_in")),
            hand_length_in=_optional_float(row.get("hand_length_in")),
            hand_width_in=_optional_float(row.get("hand_width_in")),
            standing_reach_in=_optional_float(row.get("standing_reach_in")),
            weight_lb=_optional_float(row.get("weight_lb")),
            max_vertical_in=_optional_float(row.get("max_vertical_in")),
            standing_vertical_in=_optional_float(row.get("standing_vertical_in")),
            school=row.get("school", ""),
            country=row.get("country", ""),
            is_international=_optional_bool(row.get("is_international")),
            is_center=_optional_bool(row.get("is_center")),
            talent_composite=_optional_float(row.get("talent_composite")),
            espn_rank=_optional_int(row.get("espn_rank")),
            model_pick_low=_optional_int(row.get("model_pick_low")),
            board_source=row.get("board_source", ""),
            talent_rank=_optional_int(row.get("talent_rank")),
            market_rank=_optional_float(row.get("market_rank")),
            talent_signal=_optional_float(row.get("talent_signal")),
            market_signal=_optional_float(row.get("market_signal")),
            divergence_gap=_optional_int(row.get("divergence_gap")),
            divergence_type=row.get("divergence_type", ""),
            divergence_reason=row.get("divergence_reason", ""),
            odds_signal=_optional_float(row.get("odds_signal")),
            odds_rank=_optional_float(row.get("odds_rank")),
            fused_score=_optional_float(row.get("fused_score")),
        )
        for row in _read_rows(data_dir / "prospects.csv")
    ]


def load_draft_order(data_dir: Path) -> list[Team]:
    return [
        Team(
            pick=int(row["pick"]),
            team=row["team"],
            abbreviation=row["abbreviation"],
            original_team=row.get("original_team", ""),
            via_trade=_optional_bool(row.get("via_trade")),
        )
        for row in _read_rows(data_dir / "draft_order.csv")
    ]


def load_team_needs(data_dir: Path) -> list[TeamNeed]:
    return [
        TeamNeed(
            abbreviation=row["abbreviation"],
            position=row["position"],
            weight=float(row["weight"]),
        )
        for row in _read_rows(data_dir / "team_needs.csv")
    ]


def load_mock_signals(data_dir: Path) -> list[MockSignal]:
    path = data_dir / "mock_signals.csv"
    if not path.exists():
        return []
    return [
        MockSignal(
            abbreviation=row["abbreviation"],
            prospect_id=row["prospect_id"],
            signal_strength=float(row["signal_strength"]),
            source=row["source"],
        )
        for row in _read_rows(path)
    ]


def load_odds_signals(data_dir: Path) -> list[OddsSignal]:
    path = data_dir / "odds_signals.csv"
    if not path.exists():
        return []
    return [
        OddsSignal(
            abbreviation=row["abbreviation"],
            prospect_id=row["prospect_id"],
            implied_prob=float(row["implied_prob"]),
            source=row["source"],
        )
        for row in _read_rows(path)
    ]


def write_predictions(path: Path, picks: Iterable[DraftPick]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(pick) for pick in picks]
    if not rows:
        raise ValueError("No predictions to write")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_trace(path: Path, trace: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")


def write_twin_report(path: Path, report: TwinReport) -> None:
    """Write a Milestone-Aware Draft Twin report as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
