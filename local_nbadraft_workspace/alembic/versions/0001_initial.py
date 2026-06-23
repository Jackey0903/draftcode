"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-23
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_norm", sa.Text(), nullable=False, unique=True),
        sa.Column("position", sa.Text()),
        sa.Column("position_bucket", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("is_international", sa.Boolean(), nullable=False),
        sa.Column("school", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "manual_player_override",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_name_norm", sa.Text(), nullable=False, unique=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("player.id")),
        sa.Column("canonical_name_norm", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "combine_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("player.id"), nullable=False),
        sa.Column("height_in", sa.Float()),
        sa.Column("wingspan_in", sa.Float()),
        sa.Column("weight_lbs", sa.Float()),
        sa.Column("vertical_max_in", sa.Float()),
        sa.Column("sprint_sec", sa.Float()),
        sa.Column("hand_length_in", sa.Float()),
        sa.Column("hand_width_in", sa.Float()),
        sa.Column("source", sa.Text()),
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
    )
    op.create_index("ix_combine_player_snapshot", "combine_measurements", ["player_id", "snapshot_date"])

    op.create_table(
        "draft_board",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("player.id"), nullable=False),
        sa.Column("pick_number", sa.Integer(), nullable=False),
        sa.Column("board_type", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text()),
        sa.Column("source_hash", sa.String(length=64)),
    )
    op.create_index("ix_draft_board_type_snapshot", "draft_board", ["board_type", "snapshot_date"])
    op.create_index(
        "ix_draft_board_player_type_snapshot",
        "draft_board",
        ["player_id", "board_type", "snapshot_date"],
    )

    op.create_table(
        "player_snapshot",
        sa.Column("snapshot_date", sa.Date(), primary_key=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("player.id"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_norm", sa.Text(), nullable=False),
        sa.Column("position", sa.Text()),
        sa.Column("position_bucket", sa.Text()),
        sa.Column("country", sa.Text()),
        sa.Column("is_international", sa.Boolean(), nullable=False),
        sa.Column("school", sa.Text()),
        sa.Column("height_in", sa.Float()),
        sa.Column("wingspan_in", sa.Float()),
        sa.Column("weight_lbs", sa.Float()),
        sa.Column("vertical_max_in", sa.Float()),
        sa.Column("sprint_sec", sa.Float()),
        sa.Column("hand_length_in", sa.Float()),
        sa.Column("hand_width_in", sa.Float()),
        sa.Column("combine_source", sa.Text()),
        sa.Column("combine_snapshot_date", sa.Date()),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_player_snapshot_date_name", "player_snapshot", ["snapshot_date", "name_norm"])

    op.create_table(
        "draft_board_snapshot",
        sa.Column("snapshot_date", sa.Date(), primary_key=True),
        sa.Column("board_type", sa.Text(), primary_key=True),
        sa.Column("player_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("player.id"), primary_key=True),
        sa.Column("pick_number", sa.Integer(), nullable=False),
        sa.Column("board_source", sa.Text()),
        sa.Column("board_snapshot_date", sa.Date(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("built_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index(
        "ix_draft_board_snapshot_pick",
        "draft_board_snapshot",
        ["snapshot_date", "board_type", "pick_number"],
    )

    op.create_table(
        "milestone_run",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "milestone_result",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("milestone_run.id"), nullable=False),
        sa.Column("question_code", sa.Text(), nullable=False),
        sa.Column("answer_int", sa.Integer()),
        sa.Column("answer_text", sa.Text()),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("debug_json", postgresql.JSONB()),
        sa.UniqueConstraint("run_id", "question_code", name="uq_milestone_result_run_question"),
    )


def downgrade() -> None:
    op.drop_table("milestone_result")
    op.drop_table("milestone_run")
    op.drop_index("ix_draft_board_snapshot_pick", table_name="draft_board_snapshot")
    op.drop_table("draft_board_snapshot")
    op.drop_index("ix_player_snapshot_date_name", table_name="player_snapshot")
    op.drop_table("player_snapshot")
    op.drop_index("ix_draft_board_player_type_snapshot", table_name="draft_board")
    op.drop_index("ix_draft_board_type_snapshot", table_name="draft_board")
    op.drop_table("draft_board")
    op.drop_index("ix_combine_player_snapshot", table_name="combine_measurements")
    op.drop_table("combine_measurements")
    op.drop_table("manual_player_override")
    op.drop_table("player")
