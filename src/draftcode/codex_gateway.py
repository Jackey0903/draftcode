from __future__ import annotations

import hmac
import json
import os
import time
import uuid
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from draftcode import llm_client

MAX_BODY_BYTES = 1_000_000


class RequestError(Exception):
    def __init__(self, status: int, message: str, error_type: str = "invalid_request_error"):
        super().__init__(message)
        self.status = status
        self.message = message
        self.error_type = error_type


class CodexGatewayHandler(BaseHTTPRequestHandler):
    server_version = "DraftCodeGateway/0.1"

    def do_GET(self) -> None:
        if not self._is_authorized():
            self._send_unauthorized()
            return

        path = urlsplit(self.path).path
        if path != "/health":
            self._send_error_json(404, "not found", error_type="not_found")
            return

        self._send_json(
            200,
            {
                "status": "ok",
                "codex_available": llm_client.available(),
            },
        )

    def do_POST(self) -> None:
        if not self._is_authorized():
            self._send_unauthorized()
            return

        path = urlsplit(self.path).path
        if path != "/v1/chat/completions":
            self._send_error_json(404, "not found", error_type="not_found")
            return

        try:
            request_body = self._read_json_body()
            prompt = _prompt_from_messages(request_body.get("messages"))
        except RequestError as exc:
            self._send_error_json(exc.status, exc.message, error_type=exc.error_type)
            return

        content = llm_client.complete(prompt)
        if content is None:
            self._send_error_json(502, "codex completion failed", error_type="bad_gateway")
            return

        model = request_body.get("model")
        if not isinstance(model, str) or not model.strip():
            model = os.getenv("DRAFTCODE_LLM_MODEL", llm_client.DEFAULT_MODEL)

        self._send_json(200, _openai_chat_response(model=model, content=content))

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("DRAFTCODE_GATEWAY_QUIET") == "1":
            return
        super().log_message(format, *args)

    def _is_authorized(self) -> bool:
        expected = os.getenv("DRAFTCODE_GATEWAY_KEY", "").strip()
        if not expected:
            return True
        header = self.headers.get("Authorization", "")
        return hmac.compare_digest(header, f"Bearer {expected}")

    def _send_unauthorized(self) -> None:
        self._send_error_json(
            401,
            "unauthorized",
            error_type="authentication_error",
            extra_headers={"WWW-Authenticate": "Bearer"},
        )

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise RequestError(400, "missing Content-Length")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise RequestError(400, "invalid Content-Length") from exc
        if length < 0:
            raise RequestError(400, "invalid Content-Length")
        if length > MAX_BODY_BYTES:
            raise RequestError(413, "request body too large")

        raw_body = self.rfile.read(length)
        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RequestError(400, "request body must be valid JSON") from exc
        if not isinstance(body, dict):
            raise RequestError(400, "request body must be a JSON object")
        return body

    def _send_error_json(
        self,
        status: int,
        message: str,
        *,
        error_type: str,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._send_json(
            status,
            {
                "error": {
                    "message": message,
                    "type": error_type,
                }
            },
            extra_headers=extra_headers,
        )

    def _send_json(
        self,
        status: int,
        payload: Mapping[str, Any],
        *,
        extra_headers: Mapping[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if extra_headers is not None:
            for name, value in extra_headers.items():
                self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str = "0.0.0.0", port: int = 8787) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), CodexGatewayHandler)


def serve(host: str = "0.0.0.0", port: int = 8787) -> None:
    server = create_server(host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _prompt_from_messages(messages: Any) -> str:
    if not isinstance(messages, list):
        raise RequestError(400, "messages must be an array")

    parts: list[str] = []
    for message in messages:
        if not isinstance(message, Mapping):
            continue
        role = message.get("role")
        if role not in {"system", "user"}:
            continue
        content = _message_content_to_text(message.get("content"))
        if content:
            parts.append(f"{str(role).upper()}:\n{content}")

    prompt = "\n\n".join(parts).strip()
    if not prompt:
        raise RequestError(400, "messages must include system or user content")
    return prompt


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, Mapping):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif isinstance(item, str):
                chunks.append(item)
        return "\n".join(chunk.strip() for chunk in chunks if chunk.strip())
    return ""


def _openai_chat_response(*, model: str, content: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
    }
