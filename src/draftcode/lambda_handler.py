from __future__ import annotations

import json
import os
from contextlib import suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.pipeline import run_prediction
from draftcode.simulate import (
    MonteCarloDraftTwin,
    ShardResult,
    SimulationConfig,
    TwinReport,
    aggregate_shards,
    simulate_shard,
)

REQUIRED_DATA_FILES = (
    "prospects.csv",
    "draft_order.csv",
    "team_needs.csv",
    "mock_signals.csv",
)
S3_DATA_DIR = Path("/tmp/draftcode-data")


def _is_http_event(event: dict[str, object]) -> bool:
    return bool(
        event.get("requestContext")
        or event.get("httpMethod")
        or event.get("version") == "2.0"
    )


def _event_params(event: dict[str, object]) -> dict[str, object]:
    params: dict[str, object] = {}
    query = event.get("queryStringParameters")
    if isinstance(query, dict):
        params.update(query)
    params.update(event)

    body = event.get("body")
    if isinstance(body, str) and body.strip():
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, dict):
            params.update(decoded)
    elif isinstance(body, dict):
        params.update(body)
    return params


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


def _load_boto3() -> Any | None:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError:
        return None
    return boto3


def _download_s3_data_dir() -> Path | None:
    prefix = os.getenv("DRAFTCODE_DATA_S3_PREFIX", "").strip().strip("/")
    if not prefix:
        return None

    bucket = os.getenv("DRAFTCODE_S3_BUCKET", "").strip()
    if not bucket:
        print(
            "DRAFTCODE_DATA_S3_PREFIX is set but DRAFTCODE_S3_BUCKET is empty; "
            "using local data"
        )
        return None

    boto3 = _load_boto3()
    if boto3 is None:
        print("DRAFTCODE_DATA_S3_PREFIX is set but boto3 is unavailable; using local data")
        return None

    try:
        S3_DATA_DIR.mkdir(parents=True, exist_ok=True)
        s3 = boto3.client("s3")
        for filename in REQUIRED_DATA_FILES:
            destination = S3_DATA_DIR / filename
            with suppress(FileNotFoundError):
                destination.unlink()
            s3.download_file(bucket, f"{prefix}/{filename}", str(destination))
    except Exception as exc:
        print(f"DraftCode S3 data download failed; using local data: {exc}")
        return None

    return S3_DATA_DIR


def _simulation_payload(data_dir: Path, config: SimulationConfig) -> dict[str, object]:
    prospects, draft_order, team_needs, mock_signals = _load_simulation_inputs(data_dir)
    report = MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
        config=config,
    ).run()
    run_id = f"run-{uuid4()}"
    generated_at = datetime.now(UTC).isoformat()
    payload = _summary_payload(
        report=report,
        run_id=run_id,
        generated_at=generated_at,
        mode="simulate",
        seed=config.seed,
    )
    _maybe_write_aws_outputs(payload)
    return payload


def _load_simulation_inputs(data_dir: Path) -> tuple:
    return (
        load_prospects(data_dir),
        load_draft_order(data_dir),
        load_team_needs(data_dir),
        load_mock_signals(data_dir),
    )


def _summary_payload(
    *,
    report: TwinReport,
    run_id: str,
    generated_at: str,
    mode: str,
    seed: int,
    shard_count: int | None = None,
) -> dict[str, object]:
    picks = [
        {
            "pick": pick.pick,
            "team": pick.team,
            "abbreviation": pick.abbreviation,
            "prospect_id": pick.prospect_id,
            "prospect_name": pick.prospect_name,
            "probability": pick.marginal_probability,
        }
        for pick in report.assigned_picks
    ]
    average_confidence = (
        sum(pick["probability"] for pick in picks) / len(picks) if picks else 0.0
    )
    payload = {
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": mode,
        "draws": report.config.draws,
        "seed": seed,
        "average_confidence": round(float(average_confidence), 4),
        "picks": picks,
        "milestones": [asdict(milestone) for milestone in report.milestones],
    }
    if shard_count is not None:
        payload["shard_count"] = shard_count
    return payload


def _prepare_swarm_payload(params: dict[str, object]) -> dict[str, object]:
    swarm_params = _merged_execution_input(params)
    run_id = str(swarm_params.get("run_id") or f"run-{uuid4()}")
    shard_count = _int_value(
        swarm_params.get("shard_count") or swarm_params.get("shards"),
        os.getenv("DRAFTCODE_SWARM_SHARDS"),
        10,
    )
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")
    total_draws = _int_value(
        swarm_params.get("total_draws") or swarm_params.get("draws"),
        os.getenv("DRAFTCODE_DRAWS"),
        1000,
    )
    draws_per_shard = _int_value(
        swarm_params.get("draws_per_shard"),
        None,
        total_draws // shard_count,
    )
    if draws_per_shard <= 0:
        raise ValueError("draws_per_shard must be positive")

    bucket = _s3_bucket(swarm_params)
    shards_prefix = str(
        swarm_params.get("shards_prefix") or f"runs/{run_id}/shards"
    ).strip("/")
    config = _simulation_config(swarm_params, draws=draws_per_shard)
    effective_draws = draws_per_shard * shard_count
    config_payload = _config_payload(config)
    shards = []
    for shard_index in range(shard_count):
        shard = {
            "action": "simulate_shard",
            "run_id": run_id,
            "bucket": bucket,
            "shards_prefix": shards_prefix,
            "shard_index": shard_index,
            **config_payload,
        }
        if "data_dir" in swarm_params:
            shard["data_dir"] = str(swarm_params["data_dir"])
        shards.append(shard)

    return {
        "run_id": run_id,
        "bucket": bucket,
        "shards_prefix": shards_prefix,
        "shard_count": shard_count,
        "draws_per_shard": draws_per_shard,
        "total_draws": total_draws,
        "effective_draws": effective_draws,
        **_config_payload(_simulation_config(swarm_params, draws=effective_draws)),
        "shards": shards,
    }


def _simulate_shard_payload(params: dict[str, object]) -> dict[str, object]:
    run_id = str(params.get("run_id") or f"run-{uuid4()}")
    shard_index = _int_param(params, "shard_index", "DRAFTCODE_SHARD_INDEX", 0)
    config = _simulation_config(params)
    data_dir = _simulation_data_dir(params)
    prospects, draft_order, team_needs, mock_signals = _load_simulation_inputs(data_dir)
    shard = simulate_shard(
        shard_index,
        config.draws,
        prospects,
        draft_order,
        team_needs,
        mock_signals,
        config,
    )

    bucket = _s3_bucket(params)
    shards_prefix = str(params.get("shards_prefix") or f"runs/{run_id}/shards").strip("/")
    key = f"{shards_prefix}/{shard_index}.json"
    wrote_s3 = _put_json_object(bucket, key, asdict(shard), required=bool(bucket))
    payload: dict[str, object] = {
        "run_id": run_id,
        "shard_index": shard_index,
        "draws": config.draws,
        "bucket": bucket,
        "key": key,
        "wrote_s3": wrote_s3,
    }
    if not wrote_s3:
        payload["shard"] = asdict(shard)
    return payload


def _aggregate_payload(params: dict[str, object]) -> dict[str, object]:
    run_id = str(params.get("run_id") or f"run-{uuid4()}")
    shard_results = _load_shard_results(params, run_id)
    total_draws = sum(shard.draws for shard in shard_results)
    config = _simulation_config(params, draws=total_draws)
    prospects, draft_order, _, _ = _load_simulation_inputs(_simulation_data_dir(params))
    report = aggregate_shards(shard_results, prospects, draft_order, config)
    generated_at = datetime.now(UTC).isoformat()
    payload = _summary_payload(
        report=report,
        run_id=run_id,
        generated_at=generated_at,
        mode="scenario_swarm",
        seed=config.seed,
        shard_count=len(shard_results),
    )
    payload["report"] = asdict(report)
    _maybe_write_aws_outputs(payload)
    return payload


def _merged_execution_input(params: dict[str, object]) -> dict[str, object]:
    execution_input = params.get("execution_input")
    if not isinstance(execution_input, dict):
        return params
    merged: dict[str, object] = dict(execution_input)
    merged.update(params)
    return merged


def _config_source(params: dict[str, object]) -> dict[str, object]:
    simulation_config = params.get("simulation_config")
    if not isinstance(simulation_config, dict):
        return params
    merged: dict[str, object] = dict(simulation_config)
    merged.update(params)
    return merged


def _simulation_config(
    params: dict[str, object],
    draws: int | None = None,
) -> SimulationConfig:
    source = _config_source(params)
    default = SimulationConfig()
    resolved_draws = (
        draws
        if draws is not None
        else _int_param(source, "draws", "DRAFTCODE_DRAWS", default.draws)
    )
    return SimulationConfig(
        draws=resolved_draws,
        seed=_int_param(source, "seed", "DRAFTCODE_SEED", default.seed),
        temperature=_float_param(
            source,
            "temperature",
            "DRAFTCODE_TEMPERATURE",
            default.temperature,
        ),
        top_k=_int_param(source, "top_k", "DRAFTCODE_TOP_K", default.top_k),
        weight_jitter=_float_param(
            source,
            "weight_jitter",
            "DRAFTCODE_WEIGHT_JITTER",
            default.weight_jitter,
        ),
        signal_jitter=_float_param(
            source,
            "signal_jitter",
            "DRAFTCODE_SIGNAL_JITTER",
            default.signal_jitter,
        ),
        need_jitter=_float_param(
            source,
            "need_jitter",
            "DRAFTCODE_NEED_JITTER",
            default.need_jitter,
        ),
        board_jitter=_float_param(
            source,
            "board_jitter",
            "DRAFTCODE_BOARD_JITTER",
            default.board_jitter,
        ),
        low_confidence_threshold=_float_param(
            source,
            "low_confidence_threshold",
            "DRAFTCODE_LOW_CONFIDENCE_THRESHOLD",
            default.low_confidence_threshold,
        ),
        wingspan_threshold=_float_param(
            source,
            "wingspan_threshold",
            "DRAFTCODE_WINGSPAN_THRESHOLD",
            default.wingspan_threshold,
        ),
    )


def _config_payload(config: SimulationConfig) -> dict[str, object]:
    return {
        "draws": config.draws,
        "seed": config.seed,
        "temperature": config.temperature,
        "top_k": config.top_k,
        "weight_jitter": config.weight_jitter,
        "signal_jitter": config.signal_jitter,
        "need_jitter": config.need_jitter,
        "board_jitter": config.board_jitter,
        "low_confidence_threshold": config.low_confidence_threshold,
        "wingspan_threshold": config.wingspan_threshold,
    }


def _s3_bucket(params: dict[str, object]) -> str:
    return str(params.get("bucket") or os.getenv("DRAFTCODE_S3_BUCKET") or "").strip()


def _put_json_object(
    bucket: str,
    key: str,
    payload: dict[str, object],
    *,
    required: bool = False,
) -> bool:
    if not bucket:
        if required:
            raise ValueError("S3 bucket is required")
        return False
    boto3 = _load_boto3()
    if boto3 is None:
        if required:
            raise RuntimeError("boto3 is unavailable")
        return False
    try:
        boto3.client("s3").put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
    except Exception:
        if required:
            raise
        return False
    return True


def _load_shard_results(params: dict[str, object], run_id: str) -> list[ShardResult]:
    inline = _inline_shard_results(params)
    if inline:
        return inline

    bucket = _s3_bucket(params)
    if not bucket:
        raise ValueError("aggregate requires a bucket or inline shard results")
    shards_prefix = str(params.get("shards_prefix") or f"runs/{run_id}/shards").strip("/")
    boto3 = _load_boto3()
    if boto3 is None:
        raise RuntimeError("boto3 is unavailable")
    s3 = boto3.client("s3")
    keys = _list_shard_keys(s3, bucket, shards_prefix)
    if not keys:
        raise ValueError(f"No shard JSON files found under s3://{bucket}/{shards_prefix}")
    shards: list[ShardResult] = []
    for key in keys:
        response = s3.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        shards.append(_shard_result_from_dict(json.loads(str(body))))
    return shards


def _inline_shard_results(params: dict[str, object]) -> list[ShardResult]:
    raw_shards = params.get("shards")
    if not isinstance(raw_shards, list):
        return []
    shards: list[ShardResult] = []
    for item in raw_shards:
        if not isinstance(item, dict):
            continue
        raw = item.get("shard", item)
        if isinstance(raw, dict) and "Payload" in raw and isinstance(raw["Payload"], dict):
            raw = raw["Payload"].get("shard", raw["Payload"])
        if isinstance(raw, dict) and {"shard_index", "draws", "pick_counts"} <= raw.keys():
            shards.append(_shard_result_from_dict(raw))
    return shards


def _list_shard_keys(s3: object, bucket: str, shards_prefix: str) -> list[str]:
    keys: list[str] = []
    request: dict[str, object] = {
        "Bucket": bucket,
        "Prefix": f"{shards_prefix.rstrip('/')}/",
    }
    while True:
        response = s3.list_objects_v2(**request)  # type: ignore[attr-defined]
        keys.extend(
            item["Key"]
            for item in response.get("Contents", [])
            if str(item.get("Key", "")).endswith(".json")
        )
        if not response.get("IsTruncated"):
            break
        request["ContinuationToken"] = response["NextContinuationToken"]
    return sorted(str(key) for key in keys)


def _shard_result_from_dict(raw: dict[str, object]) -> ShardResult:
    return ShardResult(
        shard_index=int(raw["shard_index"]),
        draws=int(raw["draws"]),
        pick_counts=[
            {str(prospect_id): int(count) for prospect_id, count in counts.items()}
            for counts in raw["pick_counts"]  # type: ignore[index, union-attr]
        ],
        prospect_counts={
            str(prospect_id): int(count)
            for prospect_id, count in raw["prospect_counts"].items()  # type: ignore[union-attr]
        },
        prospect_team_counts={
            str(prospect_id): {
                str(abbreviation): int(count)
                for abbreviation, count in team_counts.items()
            }
            for prospect_id, team_counts in raw["prospect_team_counts"].items()  # type: ignore[union-attr]
        },
        milestone_values={
            str(milestone_id): list(values)
            for milestone_id, values in raw["milestone_values"].items()  # type: ignore[union-attr]
        },
    )


def _maybe_write_aws_outputs(payload: dict[str, object]) -> None:
    boto3 = _load_boto3()
    if boto3 is None:
        return

    run_id = str(payload["run_id"])
    bucket = os.getenv("DRAFTCODE_S3_BUCKET")
    if bucket:
        with suppress(Exception):
            boto3.client("s3").put_object(
                Bucket=bucket,
                Key=f"runs/{run_id}/twin.json",
                Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json; charset=utf-8",
            )

    table_name = os.getenv("DRAFTCODE_DYNAMODB_TABLE")
    if table_name:
        with suppress(Exception):
            boto3.resource("dynamodb").Table(table_name).put_item(
                Item={
                    "run_id": run_id,
                    "created_at": str(payload["generated_at"]),
                    "mode": str(payload["mode"]),
                    "draws": int(payload["draws"]),
                    "average_confidence": str(payload["average_confidence"]),
                    "status": "completed",
                }
            )


def _int_param(params: dict[str, object], key: str, env_key: str, default: int) -> int:
    return _int_value(params.get(key), os.getenv(env_key), default)


def _float_param(
    params: dict[str, object],
    key: str,
    env_key: str,
    default: float,
) -> float:
    raw = params.get(key)
    if raw is None or raw == "":
        raw = os.getenv(env_key)
    if raw is None or raw == "":
        return default
    return float(str(raw))


def _int_value(raw: object, env_raw: object, default: int) -> int:
    if raw is None or raw == "":
        raw = env_raw
    if raw is None or raw == "":
        return default
    return int(str(raw))


def _data_dir(params: dict[str, object]) -> Path:
    return Path(
        str(params.get("data_dir") or os.getenv("DRAFTCODE_DATA_DIR", "/var/task/data/sample"))
    )


def _simulation_data_dir(params: dict[str, object]) -> Path:
    return _download_s3_data_dir() or _data_dir(params)


def _bedrock_ping_payload(params: dict[str, object]) -> dict[str, object]:
    model_id = str(
        params.get("model_id")
        or os.getenv("DRAFTCODE_BEDROCK_MODEL_ID")
        or "anthropic.claude-opus-4-8"
    )
    boto3 = _load_boto3()
    if boto3 is None:
        return {"ok": False, "error": "boto3 unavailable"}
    try:
        client = boto3.client("bedrock-runtime")
        body = json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 30,
                "messages": [{"role": "user", "content": "Reply with exactly: PONG"}],
            }
        )
        response = client.invoke_model(modelId=model_id, body=body)
        raw = response["body"].read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        text = "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        )
        return {"ok": True, "model_id": model_id, "text": text, "usage": data.get("usage")}
    except Exception as exc:
        return {"ok": False, "model_id": model_id, "error": str(exc)}


def handler(event: dict[str, object], context: object) -> dict[str, object]:
    event = event or {}
    params = _event_params(event)
    action = str(params.get("action") or "predict")
    if action == "simulate":
        payload = _simulation_payload(
            data_dir=_simulation_data_dir(params),
            config=_simulation_config(params),
        )
    elif action == "prepare_swarm":
        payload = _prepare_swarm_payload(params)
    elif action == "simulate_shard":
        payload = _simulate_shard_payload(params)
    elif action == "aggregate":
        payload = _aggregate_payload(params)
    elif action == "bedrock_ping":
        payload = _bedrock_ping_payload(params)
    else:
        payload = _prediction_payload(_data_dir(params))
    if not _is_http_event(event):
        return payload

    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload, ensure_ascii=False),
    }
