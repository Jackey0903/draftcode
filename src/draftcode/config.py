from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("DRAFTCODE_DATA_DIR", "data/sample"))
    output_dir: Path = Path(os.getenv("DRAFTCODE_OUTPUT_DIR", "outputs"))
    aws_region: str = os.getenv("DRAFTCODE_AWS_REGION", "us-east-1")
    s3_bucket: str | None = os.getenv("DRAFTCODE_S3_BUCKET") or None
    dynamodb_table: str | None = os.getenv("DRAFTCODE_DYNAMODB_TABLE") or None
    bedrock_model_id: str = os.getenv(
        "DRAFTCODE_BEDROCK_MODEL_ID",
        "anthropic.claude-3-5-sonnet-20240620-v1:0",
    )


def get_settings() -> Settings:
    return Settings()
