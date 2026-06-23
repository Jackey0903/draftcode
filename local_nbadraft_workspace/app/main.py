from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_session
from app.milestones import compute_milestones
from app.schemas import (
    ComputeRequest,
    ComputeResponse,
    MilestoneResultOut,
    Mode,
    SnapshotDebugResponse,
)
from app.snapshot import build_snapshot


app = FastAPI(
    title="NBA Draft Milestone Agent DB",
    version="0.1.0",
    description="Deterministic snapshot-based NBA draft milestone answer API.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/milestone/compute", response_model=ComputeResponse)
def compute(
    request: ComputeRequest,
    session: Session = Depends(get_session),
) -> ComputeResponse:
    try:
        run, answers, snapshot = compute_milestones(
            session=session,
            snapshot_date=request.snapshot_date,
            mode=request.mode,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

    return ComputeResponse(
        run_id=run.id,
        snapshot_date=snapshot.snapshot_date,
        mode=snapshot.mode,  # type: ignore[arg-type]
        source_hash=snapshot.source_hash,
        results=[
            MilestoneResultOut(
                question=answer.question_code,
                answer=answer.answer,
                answer_int=answer.answer_int,
                answer_text=answer.answer_text,
                confidence=answer.confidence,
            )
            for answer in answers
        ],
    )


@app.get("/snapshot/{snapshot_date}", response_model=SnapshotDebugResponse)
def snapshot_debug(
    snapshot_date: date,
    mode: Mode = Query(default="projected"),
    session: Session = Depends(get_session),
) -> SnapshotDebugResponse:
    try:
        snapshot = build_snapshot(session, snapshot_date, mode)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        session.rollback()
        raise

    return SnapshotDebugResponse(
        snapshot_date=snapshot.snapshot_date,
        mode=snapshot.mode,  # type: ignore[arg-type]
        player_count=snapshot.player_count,
        board_count=snapshot.board_count,
        player_source_hash=snapshot.player_source_hash,
        board_source_hash=snapshot.board_source_hash,
        source_hash=snapshot.source_hash,
    )
