from __future__ import annotations

import json
import os
from pathlib import Path

from draftcode.pipeline import run_prediction


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    data_dir = Path(os.getenv("DRAFTCODE_DATA_DIR", "/var/task/data/sample"))
    picks = run_prediction(data_dir)
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps([pick.__dict__ for pick in picks], ensure_ascii=False),
    }
