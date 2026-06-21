from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from draftcode.config import get_settings
from draftcode.pipeline import run_prediction

app = FastAPI(title="DraftCode NBA Draft Agent")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/predictions")
def predictions(data_dir: str | None = None) -> list[dict[str, object]]:
    settings = get_settings()
    resolved = Path(data_dir) if data_dir else settings.data_dir
    return [pick.__dict__ for pick in run_prediction(resolved)]
