from __future__ import annotations

import json
from io import BytesIO
from typing import Any
from urllib.error import URLError

from draftcode import codex_gateway, llm_client


class FakeSocket:
    def __init__(self, request: bytes):
        self.input = BytesIO(request)
        self.output = BytesIO()

    def makefile(self, mode: str, buffering: int | None = None):
        if "r" in mode:
            return self.input
        return self.output

    def sendall(self, data: bytes) -> None:
        self.output.write(data)


def request_json(
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    encoded_body = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = dict(headers or {})
    request_headers.setdefault("Host", "testserver")
    if body is not None:
        request_headers.setdefault("Content-Type", "application/json")
        request_headers["Content-Length"] = str(len(encoded_body or b""))

    header_lines = [
        f"{method} {path} HTTP/1.1",
        *[f"{name}: {value}" for name, value in request_headers.items()],
    ]
    request_head = "\r\n".join(header_lines)
    raw_request = request_head.encode("utf-8") + b"\r\n\r\n" + (encoded_body or b"")
    socket = FakeSocket(raw_request)

    codex_gateway.CodexGatewayHandler(socket, ("127.0.0.1", 12345), object())

    raw_response = socket.output.getvalue()
    response_head, response_body = raw_response.split(b"\r\n\r\n", 1)
    header_lines = response_head.decode("iso-8859-1").split("\r\n")
    status = int(header_lines[0].split()[1])
    response_headers = {
        name: value
        for line in header_lines[1:]
        if ": " in line
        for name, value in [line.split(": ", 1)]
    }
    return status, response_headers, json.loads(response_body.decode("utf-8"))


def test_gateway_health_reports_codex_availability(monkeypatch) -> None:
    monkeypatch.delenv("DRAFTCODE_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("DRAFTCODE_GATEWAY_QUIET", "1")
    monkeypatch.setattr(codex_gateway.llm_client, "available", lambda: True)

    status, headers, body = request_json("GET", "/health")

    assert status == 200
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert body == {"status": "ok", "codex_available": True}


def test_gateway_chat_completions_returns_openai_shape(monkeypatch) -> None:
    monkeypatch.delenv("DRAFTCODE_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("DRAFTCODE_GATEWAY_QUIET", "1")
    captured: dict[str, str] = {}

    def fake_complete(prompt: str, schema=None, timeout: int = 180) -> str:
        captured["prompt"] = prompt
        return "gateway answer"

    monkeypatch.setattr(codex_gateway.llm_client, "complete", fake_complete)
    payload = {
        "model": "draftcode-test",
        "messages": [
            {"role": "system", "content": "You are terse."},
            {"role": "user", "content": "Pick for UTA?"},
            {"role": "assistant", "content": "Ignored prior answer."},
        ],
    }

    status, _headers, body = request_json("POST", "/v1/chat/completions", payload)

    assert status == 200
    assert body["object"] == "chat.completion"
    assert body["model"] == "draftcode-test"
    assert body["choices"] == [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "gateway answer"},
            "finish_reason": "stop",
        }
    ]
    assert body["id"].startswith("chatcmpl-")
    assert isinstance(body["created"], int)
    assert captured["prompt"] == "SYSTEM:\nYou are terse.\n\nUSER:\nPick for UTA?"


def test_gateway_chat_completion_failure_returns_502(monkeypatch) -> None:
    monkeypatch.delenv("DRAFTCODE_GATEWAY_KEY", raising=False)
    monkeypatch.setenv("DRAFTCODE_GATEWAY_QUIET", "1")
    monkeypatch.setattr(codex_gateway.llm_client, "complete", lambda *args, **kwargs: None)

    status, _headers, body = request_json(
        "POST",
        "/v1/chat/completions",
        {"messages": [{"role": "user", "content": "hello"}]},
    )

    assert status == 502
    assert body["error"]["type"] == "bad_gateway"


def test_gateway_requires_bearer_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("DRAFTCODE_GATEWAY_KEY", "secret")
    monkeypatch.setenv("DRAFTCODE_GATEWAY_QUIET", "1")

    def fail_complete(*args, **kwargs):
        raise AssertionError("unauthorized requests must not call Codex")

    monkeypatch.setattr(codex_gateway.llm_client, "complete", fail_complete)

    status, headers, body = request_json(
        "POST",
        "/v1/chat/completions",
        {"messages": [{"role": "user", "content": "hello"}]},
    )

    assert status == 401
    assert headers["WWW-Authenticate"] == "Bearer"
    assert body["error"]["type"] == "authentication_error"


def test_llm_client_remote_mode_posts_openai_request(monkeypatch) -> None:
    monkeypatch.setenv("DRAFTCODE_LLM_BASE_URL", "http://gateway.local")
    monkeypatch.setenv("DRAFTCODE_LLM_API_KEY", "remote-key")
    monkeypatch.delenv("DRAFTCODE_LLM_DISABLED", raising=False)

    def fail_available() -> bool:
        raise AssertionError("remote mode must not check local Codex availability")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": " remote answer ",
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    captured: dict[str, Any] = {}

    def fake_urlopen(request, timeout: int):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(llm_client, "available", fail_available)
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    result = llm_client.complete("Return JSON.", schema={"type": "object"}, timeout=7)

    assert result == "remote answer"
    assert captured["url"] == "http://gateway.local/v1/chat/completions"
    assert captured["timeout"] == 7
    assert captured["authorization"] == "Bearer remote-key"
    assert captured["body"]["messages"] == [
        {
            "role": "user",
            "content": (
                "Return JSON.\n\nRespond with ONLY a single-line valid JSON object matching "
                "this JSON Schema (no prose, no markdown code fences):\n"
                '{"type": "object"}'
            ),
        }
    ]


def test_llm_client_remote_mode_returns_none_on_http_failure(monkeypatch) -> None:
    monkeypatch.setenv("DRAFTCODE_LLM_BASE_URL", "http://gateway.local")
    monkeypatch.delenv("DRAFTCODE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DRAFTCODE_LLM_DISABLED", raising=False)

    def fake_urlopen(*args, **kwargs):
        raise URLError("down")

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    assert llm_client.complete("hello", timeout=1) is None
