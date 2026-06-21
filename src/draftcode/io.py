from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, TypeVar

from draftcode.schemas import DraftPick, MockSignal, Prospect, Team, TeamNeed

T = TypeVar("T")


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required data file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
        )
        for row in _read_rows(data_dir / "prospects.csv")
    ]


def load_draft_order(data_dir: Path) -> list[Team]:
    return [
        Team(pick=int(row["pick"]), team=row["team"], abbreviation=row["abbreviation"])
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
