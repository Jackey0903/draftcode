from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    CombineMeasurement,
    DraftBoard,
    DraftBoardSnapshot,
    Player,
    PlayerSnapshot,
)


@dataclass(frozen=True)
class SnapshotSummary:
    snapshot_date: date
    mode: str
    player_count: int
    board_count: int
    player_source_hash: str
    board_source_hash: str
    source_hash: str


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _aggregate_hash(row_hashes: list[str]) -> str:
    return _stable_hash(sorted(row_hashes))


def normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in {"actual", "projected"}:
        raise ValueError("mode must be 'actual' or 'projected'")
    return normalized


def build_player_snapshot(session: Session, snapshot_date: date) -> tuple[int, str]:
    cm = CombineMeasurement
    ranked_combine = (
        select(
            cm.player_id.label("cm_player_id"),
            cm.height_in,
            cm.wingspan_in,
            cm.weight_lbs,
            cm.vertical_max_in,
            cm.sprint_sec,
            cm.hand_length_in,
            cm.hand_width_in,
            cm.source.label("combine_source"),
            cm.source_hash.label("combine_source_hash"),
            cm.snapshot_date.label("combine_snapshot_date"),
            func.row_number()
            .over(
                partition_by=cm.player_id,
                order_by=(cm.snapshot_date.desc(), cm.id.desc()),
            )
            .label("rn"),
        )
        .where(cm.snapshot_date <= snapshot_date)
        .subquery()
    )

    session.execute(delete(PlayerSnapshot).where(PlayerSnapshot.snapshot_date == snapshot_date))

    rows = session.execute(
        select(
            Player.id.label("player_id"),
            Player.name,
            Player.name_norm,
            Player.position,
            Player.position_bucket,
            Player.country,
            Player.is_international,
            Player.school,
            ranked_combine.c.height_in,
            ranked_combine.c.wingspan_in,
            ranked_combine.c.weight_lbs,
            ranked_combine.c.vertical_max_in,
            ranked_combine.c.sprint_sec,
            ranked_combine.c.hand_length_in,
            ranked_combine.c.hand_width_in,
            ranked_combine.c.combine_source,
            ranked_combine.c.combine_source_hash,
            ranked_combine.c.combine_snapshot_date,
        )
        .outerjoin(
            ranked_combine,
            (Player.id == ranked_combine.c.cm_player_id) & (ranked_combine.c.rn == 1),
        )
        .order_by(Player.name_norm)
    ).all()

    snapshots: list[PlayerSnapshot] = []
    row_hashes: list[str] = []
    for row in rows:
        data = dict(row._mapping)
        row_hash = _stable_hash(data)
        row_hashes.append(row_hash)
        snapshots.append(
            PlayerSnapshot(
                snapshot_date=snapshot_date,
                player_id=data["player_id"],
                name=data["name"],
                name_norm=data["name_norm"],
                position=data["position"],
                position_bucket=data["position_bucket"],
                country=data["country"],
                is_international=bool(data["is_international"]),
                school=data["school"],
                height_in=data["height_in"],
                wingspan_in=data["wingspan_in"],
                weight_lbs=data["weight_lbs"],
                vertical_max_in=data["vertical_max_in"],
                sprint_sec=data["sprint_sec"],
                hand_length_in=data["hand_length_in"],
                hand_width_in=data["hand_width_in"],
                combine_source=data["combine_source"],
                combine_snapshot_date=data["combine_snapshot_date"],
                source_hash=row_hash,
            )
        )

    session.add_all(snapshots)
    session.flush()
    return len(snapshots), _aggregate_hash(row_hashes)


def build_draft_board_snapshot(session: Session, snapshot_date: date, mode: str) -> tuple[int, str]:
    mode = normalize_mode(mode)
    db = DraftBoard
    ranked_board = (
        select(
            db.player_id,
            db.pick_number,
            db.board_type,
            db.snapshot_date.label("board_snapshot_date"),
            db.source.label("board_source"),
            db.source_hash.label("board_source_hash"),
            func.row_number()
            .over(
                partition_by=db.player_id,
                order_by=(db.snapshot_date.desc(), db.pick_number.asc(), db.id.desc()),
            )
            .label("rn"),
        )
        .where(db.snapshot_date <= snapshot_date, db.board_type == mode)
        .subquery()
    )

    session.execute(
        delete(DraftBoardSnapshot).where(
            DraftBoardSnapshot.snapshot_date == snapshot_date,
            DraftBoardSnapshot.board_type == mode,
        )
    )

    rows = session.execute(
        select(
            ranked_board.c.player_id,
            ranked_board.c.pick_number,
            ranked_board.c.board_type,
            ranked_board.c.board_snapshot_date,
            ranked_board.c.board_source,
            ranked_board.c.board_source_hash,
        )
        .where(ranked_board.c.rn == 1)
        .order_by(ranked_board.c.pick_number)
    ).all()

    snapshots: list[DraftBoardSnapshot] = []
    row_hashes: list[str] = []
    for row in rows:
        data = dict(row._mapping)
        row_hash = _stable_hash(data)
        row_hashes.append(row_hash)
        snapshots.append(
            DraftBoardSnapshot(
                snapshot_date=snapshot_date,
                board_type=mode,
                player_id=data["player_id"],
                pick_number=data["pick_number"],
                board_source=data["board_source"],
                board_snapshot_date=data["board_snapshot_date"],
                source_hash=row_hash,
            )
        )

    session.add_all(snapshots)
    session.flush()
    return len(snapshots), _aggregate_hash(row_hashes)


def build_snapshot(session: Session, snapshot_date: date, mode: str) -> SnapshotSummary:
    mode = normalize_mode(mode)
    player_count, player_hash = build_player_snapshot(session, snapshot_date)
    board_count, board_hash = build_draft_board_snapshot(session, snapshot_date, mode)
    source_hash = _stable_hash(
        {
            "snapshot_date": snapshot_date.isoformat(),
            "mode": mode,
            "player_source_hash": player_hash,
            "board_source_hash": board_hash,
        }
    )
    return SnapshotSummary(
        snapshot_date=snapshot_date,
        mode=mode,
        player_count=player_count,
        board_count=board_count,
        player_source_hash=player_hash,
        board_source_hash=board_hash,
        source_hash=source_hash,
    )
