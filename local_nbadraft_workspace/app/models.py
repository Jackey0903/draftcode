from __future__ import annotations

from datetime import date, datetime
import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, JSON, TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class JSONType(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "player"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    position: Mapped[str | None] = mapped_column(Text)
    position_bucket: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    is_international: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    school: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    measurements: Mapped[list[CombineMeasurement]] = relationship(back_populates="player")
    board_entries: Mapped[list[DraftBoard]] = relationship(back_populates="player")


class ManualPlayerOverride(Base):
    __tablename__ = "manual_player_override"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    raw_name_norm: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    player_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("player.id"))
    canonical_name_norm: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CombineMeasurement(Base):
    __tablename__ = "combine_measurements"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("player.id"), nullable=False)
    height_in: Mapped[float | None] = mapped_column(Float)
    wingspan_in: Mapped[float | None] = mapped_column(Float)
    weight_lbs: Mapped[float | None] = mapped_column(Float)
    vertical_max_in: Mapped[float | None] = mapped_column(Float)
    sprint_sec: Mapped[float | None] = mapped_column(Float)
    hand_length_in: Mapped[float | None] = mapped_column(Float)
    hand_width_in: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    player: Mapped[Player] = relationship(back_populates="measurements")

    __table_args__ = (
        Index("ix_combine_player_snapshot", "player_id", "snapshot_date"),
    )


class DraftBoard(Base):
    __tablename__ = "draft_board"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    player_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("player.id"), nullable=False)
    pick_number: Mapped[int] = mapped_column(Integer, nullable=False)
    board_type: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64))

    player: Mapped[Player] = relationship(back_populates="board_entries")

    __table_args__ = (
        Index("ix_draft_board_type_snapshot", "board_type", "snapshot_date"),
        Index("ix_draft_board_player_type_snapshot", "player_id", "board_type", "snapshot_date"),
    )


class PlayerSnapshot(Base):
    __tablename__ = "player_snapshot"

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    player_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("player.id"), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_norm: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[str | None] = mapped_column(Text)
    position_bucket: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    is_international: Mapped[bool] = mapped_column(Boolean, nullable=False)
    school: Mapped[str | None] = mapped_column(Text)
    height_in: Mapped[float | None] = mapped_column(Float)
    wingspan_in: Mapped[float | None] = mapped_column(Float)
    weight_lbs: Mapped[float | None] = mapped_column(Float)
    vertical_max_in: Mapped[float | None] = mapped_column(Float)
    sprint_sec: Mapped[float | None] = mapped_column(Float)
    hand_length_in: Mapped[float | None] = mapped_column(Float)
    hand_width_in: Mapped[float | None] = mapped_column(Float)
    combine_source: Mapped[str | None] = mapped_column(Text)
    combine_snapshot_date: Mapped[date | None] = mapped_column(Date)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_player_snapshot_date_name", "snapshot_date", "name_norm"),
    )


class DraftBoardSnapshot(Base):
    __tablename__ = "draft_board_snapshot"

    snapshot_date: Mapped[date] = mapped_column(Date, primary_key=True)
    board_type: Mapped[str] = mapped_column(Text, primary_key=True)
    player_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("player.id"), primary_key=True)
    pick_number: Mapped[int] = mapped_column(Integer, nullable=False)
    board_source: Mapped[str | None] = mapped_column(Text)
    board_snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    built_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_draft_board_snapshot_pick", "snapshot_date", "board_type", "pick_number"),
    )


class MilestoneRun(Base):
    __tablename__ = "milestone_run"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    results: Mapped[list[MilestoneResult]] = relationship(back_populates="run")


class MilestoneResult(Base):
    __tablename__ = "milestone_result"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("milestone_run.id"), nullable=False)
    question_code: Mapped[str] = mapped_column(Text, nullable=False)
    answer_int: Mapped[int | None] = mapped_column(Integer)
    answer_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    debug_json: Mapped[dict | None] = mapped_column(JSONType())

    run: Mapped[MilestoneRun] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint("run_id", "question_code", name="uq_milestone_result_run_question"),
    )
