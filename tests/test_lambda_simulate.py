from __future__ import annotations

import shutil
import sys
from pathlib import Path

from draftcode.io import load_draft_order
from draftcode.lambda_handler import handler

SAMPLE_DIR = Path("data/sample")


class StubS3Client:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, str, str]] = []
        self.puts: list[dict[str, object]] = []

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        self.downloads.append((bucket, key, filename))
        shutil.copyfile(SAMPLE_DIR / Path(key).name, filename)

    def put_object(self, **kwargs: object) -> None:
        self.puts.append(kwargs)


class StubBoto3:
    def __init__(self, s3: StubS3Client) -> None:
        self.s3 = s3

    def client(self, service_name: str) -> StubS3Client:
        assert service_name == "s3"
        return self.s3


def test_lambda_handler_supports_simulate_action(monkeypatch) -> None:
    monkeypatch.delenv("DRAFTCODE_S3_BUCKET", raising=False)
    monkeypatch.delenv("DRAFTCODE_DYNAMODB_TABLE", raising=False)

    response = handler(
        {"action": "simulate", "data_dir": str(SAMPLE_DIR), "draws": 50},
        None,
    )

    assert str(response["run_id"]).startswith("run-")
    assert response["mode"] == "simulate"
    assert response["draws"] == 50
    assert response["seed"] == 42
    assert len(response["picks"]) == len(load_draft_order(SAMPLE_DIR))
    assert len({pick["prospect_id"] for pick in response["picks"]}) == len(
        response["picks"]
    )
    assert {milestone["id"] for milestone in response["milestones"]} == {
        f"Q{index}" for index in range(1, 8)
    }


def test_lambda_handler_simulate_is_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("DRAFTCODE_S3_BUCKET", raising=False)
    monkeypatch.delenv("DRAFTCODE_DYNAMODB_TABLE", raising=False)
    event = {"action": "simulate", "data_dir": str(SAMPLE_DIR), "draws": 50, "seed": 123}

    first = handler(event, None)
    second = handler(event, None)

    assert first["picks"] == second["picks"]
    assert first["milestones"] == second["milestones"]
    assert first["average_confidence"] == second["average_confidence"]


def test_lambda_handler_downloads_s3_data_when_prefix_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    s3 = StubS3Client()
    monkeypatch.setitem(sys.modules, "boto3", StubBoto3(s3))
    monkeypatch.setenv("DRAFTCODE_DATA_S3_PREFIX", "processed")
    monkeypatch.setenv("DRAFTCODE_S3_BUCKET", "draft-bucket")
    monkeypatch.setenv("DRAFTCODE_DATA_DIR", str(tmp_path / "missing-local-data"))
    monkeypatch.delenv("DRAFTCODE_DYNAMODB_TABLE", raising=False)

    response = handler({"action": "simulate", "draws": 20}, None)

    assert response["mode"] == "simulate"
    assert [download[:2] for download in s3.downloads] == [
        ("draft-bucket", "processed/prospects.csv"),
        ("draft-bucket", "processed/draft_order.csv"),
        ("draft-bucket", "processed/team_needs.csv"),
        ("draft-bucket", "processed/mock_signals.csv"),
    ]
    assert s3.puts


def test_lambda_handler_uses_local_data_without_s3_prefix(monkeypatch) -> None:
    class FailingBoto3:
        called = False

        def client(self, service_name: str) -> object:
            self.called = True
            raise AssertionError(f"unexpected boto3 client call for {service_name}")

    boto3 = FailingBoto3()
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    monkeypatch.delenv("DRAFTCODE_DATA_S3_PREFIX", raising=False)
    monkeypatch.delenv("DRAFTCODE_S3_BUCKET", raising=False)
    monkeypatch.delenv("DRAFTCODE_DYNAMODB_TABLE", raising=False)
    monkeypatch.setenv("DRAFTCODE_DATA_DIR", str(SAMPLE_DIR))

    response = handler({"action": "simulate", "draws": 20}, None)

    assert response["mode"] == "simulate"
    assert len(response["picks"]) == len(load_draft_order(SAMPLE_DIR))
    assert boto3.called is False
