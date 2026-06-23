from __future__ import annotations

from datetime import date
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field


Mode = Literal["actual", "projected"]


class ComputeRequest(BaseModel):
    snapshot_date: date
    mode: Mode = "projected"


class MilestoneResultOut(BaseModel):
    question: str
    answer: int | str | None
    answer_int: int | None = None
    answer_text: str | None = None
    confidence: float = Field(ge=0, le=1)


class ComputeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    snapshot_date: date
    mode: Mode
    source_hash: str
    results: list[MilestoneResultOut]


class SnapshotDebugResponse(BaseModel):
    snapshot_date: date
    mode: Mode
    player_count: int
    board_count: int
    player_source_hash: str
    board_source_hash: str
    source_hash: str
