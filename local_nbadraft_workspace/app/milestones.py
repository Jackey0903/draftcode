from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import MilestoneResult, MilestoneRun
from app.snapshot import SnapshotSummary, build_snapshot, normalize_mode


@dataclass(frozen=True)
class MilestoneAnswer:
    question_code: str
    answer_int: int | None
    answer_text: str | None
    confidence: float
    debug_json: dict

    @property
    def answer(self) -> int | str | None:
        return self.answer_text if self.answer_text is not None else self.answer_int


BASE_DEBUG = {
    "computed_from": ["player_snapshot", "draft_board_snapshot"],
    "deterministic": True,
}


def _debug(question_code: str, snapshot_date: date, mode: str, source_hash: str) -> dict:
    return {
        **BASE_DEBUG,
        "question_code": question_code,
        "snapshot_date": snapshot_date.isoformat(),
        "mode": mode,
        "source_hash": source_hash,
    }


def _count_query(session: Session, sql: str, params: dict) -> int:
    value = session.execute(text(sql), params).scalar_one()
    return int(value or 0)


def compute_q1(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    answer = _count_query(
        session,
        """
        SELECT COUNT(*) AS answer_int
        FROM draft_board_snapshot dbs
        JOIN player_snapshot ps
          ON ps.snapshot_date = dbs.snapshot_date
         AND ps.player_id = dbs.player_id
        WHERE dbs.snapshot_date = :snapshot_date
          AND dbs.board_type = :mode
          AND dbs.pick_number BETWEEN 4 AND 14
          AND ps.height_in IS NOT NULL
          AND ps.wingspan_in IS NOT NULL
          AND (ps.wingspan_in - ps.height_in) >= 5
        """,
        {"snapshot_date": snapshot_date, "mode": mode},
    )
    return MilestoneAnswer("Q1", answer, None, 1.0, _debug("Q1", snapshot_date, mode, source_hash))


def compute_q2(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    answer = _count_query(
        session,
        """
        WITH top_vertical AS (
          SELECT
            player_id,
            ROW_NUMBER() OVER (ORDER BY vertical_max_in DESC, name_norm ASC) AS rn
          FROM player_snapshot
          WHERE snapshot_date = :snapshot_date
            AND vertical_max_in IS NOT NULL
        )
        SELECT COUNT(*) AS answer_int
        FROM top_vertical tv
        JOIN draft_board_snapshot dbs
          ON dbs.player_id = tv.player_id
         AND dbs.snapshot_date = :snapshot_date
         AND dbs.board_type = :mode
        WHERE tv.rn <= 3
          AND dbs.pick_number BETWEEN 1 AND 30
        """,
        {"snapshot_date": snapshot_date, "mode": mode},
    )
    return MilestoneAnswer("Q2", answer, None, 1.0, _debug("Q2", snapshot_date, mode, source_hash))


def compute_q3(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    answer = _count_query(
        session,
        """
        SELECT COUNT(*) AS answer_int
        FROM draft_board_snapshot dbs
        JOIN player_snapshot ps
          ON ps.snapshot_date = dbs.snapshot_date
         AND ps.player_id = dbs.player_id
        WHERE dbs.snapshot_date = :snapshot_date
          AND dbs.board_type = :mode
          AND dbs.pick_number BETWEEN 1 AND 30
          AND (
            COALESCE(ps.position_bucket, '') = 'C'
            OR LOWER(COALESCE(ps.position, '')) LIKE '%center%'
          )
        """,
        {"snapshot_date": snapshot_date, "mode": mode},
    )
    return MilestoneAnswer("Q3", answer, None, 1.0, _debug("Q3", snapshot_date, mode, source_hash))


def compute_q4(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    value = session.execute(
        text(
            """
            SELECT MIN(dbs.pick_number) AS answer_int
            FROM draft_board_snapshot dbs
            JOIN player_snapshot ps
              ON ps.snapshot_date = dbs.snapshot_date
             AND ps.player_id = dbs.player_id
            WHERE dbs.snapshot_date = :snapshot_date
              AND dbs.board_type = :mode
              AND dbs.pick_number BETWEEN 4 AND 30
              AND (
                COALESCE(ps.position_bucket, '') = 'C'
                OR LOWER(COALESCE(ps.position, '')) LIKE '%center%'
              )
            """
        ),
        {"snapshot_date": snapshot_date, "mode": mode},
    ).scalar_one()
    answer = int(value) if value is not None else None
    return MilestoneAnswer("Q4", answer, None, 1.0, _debug("Q4", snapshot_date, mode, source_hash))


def compute_q5(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    answer = _count_query(
        session,
        """
        SELECT COUNT(*) AS answer_int
        FROM draft_board_snapshot dbs
        JOIN player_snapshot ps
          ON ps.snapshot_date = dbs.snapshot_date
         AND ps.player_id = dbs.player_id
        WHERE dbs.snapshot_date = :snapshot_date
          AND dbs.board_type = :mode
          AND dbs.pick_number BETWEEN 1 AND 30
          AND ps.is_international = :is_true
        """,
        {"snapshot_date": snapshot_date, "mode": mode, "is_true": True},
    )
    return MilestoneAnswer("Q5", answer, None, 1.0, _debug("Q5", snapshot_date, mode, source_hash))


def compute_q6(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    row = session.execute(
        text(
            """
            WITH school_counts AS (
              SELECT
                COALESCE(NULLIF(ps.school, ''), 'Unknown') AS school,
                COUNT(*) AS first_round_count
              FROM draft_board_snapshot dbs
              JOIN player_snapshot ps
                ON ps.snapshot_date = dbs.snapshot_date
               AND ps.player_id = dbs.player_id
              WHERE dbs.snapshot_date = :snapshot_date
                AND dbs.board_type = :mode
                AND dbs.pick_number BETWEEN 1 AND 30
              GROUP BY COALESCE(NULLIF(ps.school, ''), 'Unknown')
            )
            SELECT school, first_round_count
            FROM school_counts
            ORDER BY first_round_count DESC, school ASC
            LIMIT 1
            """
        ),
        {"snapshot_date": snapshot_date, "mode": mode},
    ).mappings().one_or_none()
    debug = _debug("Q6", snapshot_date, mode, source_hash)
    if row is None:
        return MilestoneAnswer("Q6", None, None, 1.0, debug)
    debug["first_round_count"] = int(row["first_round_count"])
    return MilestoneAnswer("Q6", int(row["first_round_count"]), row["school"], 1.0, debug)


def compute_q7(session: Session, snapshot_date: date, mode: str, source_hash: str) -> MilestoneAnswer:
    answer = _count_query(
        session,
        """
        WITH top_hands AS (
          SELECT
            player_id,
            ROW_NUMBER() OVER (ORDER BY hand_length_in DESC, name_norm ASC) AS rn
          FROM player_snapshot
          WHERE snapshot_date = :snapshot_date
            AND hand_length_in IS NOT NULL
        )
        SELECT COUNT(*) AS answer_int
        FROM top_hands th
        JOIN draft_board_snapshot dbs
          ON dbs.player_id = th.player_id
         AND dbs.snapshot_date = :snapshot_date
         AND dbs.board_type = :mode
        WHERE th.rn <= 5
          AND dbs.pick_number BETWEEN 1 AND 30
        """,
        {"snapshot_date": snapshot_date, "mode": mode},
    )
    return MilestoneAnswer("Q7", answer, None, 1.0, _debug("Q7", snapshot_date, mode, source_hash))


MILESTONE_FUNCTIONS = [
    compute_q1,
    compute_q2,
    compute_q3,
    compute_q4,
    compute_q5,
    compute_q6,
    compute_q7,
]


def compute_milestones(
    session: Session,
    snapshot_date: date,
    mode: str,
) -> tuple[MilestoneRun, list[MilestoneAnswer], SnapshotSummary]:
    mode = normalize_mode(mode)
    snapshot = build_snapshot(session, snapshot_date, mode)

    run = MilestoneRun(
        id=uuid.uuid4(),
        snapshot_date=snapshot_date,
        mode=mode,
        source_hash=snapshot.source_hash,
    )
    session.add(run)
    session.flush()

    answers = [
        milestone_fn(session, snapshot_date, mode, snapshot.source_hash)
        for milestone_fn in MILESTONE_FUNCTIONS
    ]
    session.add_all(
        [
            MilestoneResult(
                run_id=run.id,
                question_code=answer.question_code,
                answer_int=answer.answer_int,
                answer_text=answer.answer_text,
                confidence=answer.confidence,
                debug_json=answer.debug_json,
            )
            for answer in answers
        ]
    )
    session.flush()
    return run, answers, snapshot
