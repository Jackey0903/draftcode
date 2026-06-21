from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Prospect:
    prospect_id: str
    name: str
    primary_position: str
    archetype: str
    consensus_rank: int
    age: float
    height_in: float
    wingspan_in: float
    usage_rate: float
    true_shooting_pct: float
    assist_rate: float
    rebound_rate: float
    stock_rate: float
    notes: str = ""


@dataclass(frozen=True)
class Team:
    pick: int
    team: str
    abbreviation: str


@dataclass(frozen=True)
class TeamNeed:
    abbreviation: str
    position: str
    weight: float


@dataclass(frozen=True)
class MockSignal:
    abbreviation: str
    prospect_id: str
    signal_strength: float
    source: str


@dataclass(frozen=True)
class DraftPick:
    pick: int
    team: str
    abbreviation: str
    prospect_id: str
    prospect_name: str
    score: float
    confidence: float
    reason: str


@dataclass(frozen=True)
class ModelWeights:
    board: float = 0.36
    pick_slot: float = 0.24
    team_need: float = 0.24
    mock_signal: float = 0.16
