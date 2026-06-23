from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from draftcode.pipeline import run_prediction


def _is_http_event(event: dict[str, object]) -> bool:
    return bool(
        event.get("requestContext")
        or event.get("httpMethod")
        or event.get("version") == "2.0"
    )


def _prediction_payload(data_dir: Path) -> dict[str, object]:
    picks = run_prediction(data_dir)
    generated_at = datetime.now(UTC).isoformat()
    return {
        "run_id": f"run-{uuid4()}",
        "generated_at": generated_at,
        "prediction_count": len(picks),
        "average_confidence": round(sum(pick.confidence for pick in picks) / len(picks), 4),
        "predictions": [pick.__dict__ for pick in picks],
    }


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    event = event or {}
    data_dir = Path(
        str(event.get("data_dir") or os.getenv("DRAFTCODE_DATA_DIR", "/var/task/data/sample"))
    )
    payload = _prediction_payload(data_dir)
    if not _is_http_event(event):
        return payload

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
