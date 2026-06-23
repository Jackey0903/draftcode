from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "gpt-5.5-codex"


def available() -> bool:
    """Return whether the Codex CLI is available on PATH."""
    return shutil.which("codex") is not None


def complete(prompt: str, schema: dict | None = None, timeout: int = 180) -> str | None:
    """Run a single gpt-5.5 completion locally or through a remote gateway.

    If ``DRAFTCODE_LLM_BASE_URL`` is set, the prompt is sent to an OpenAI-compatible
    HTTP endpoint. Otherwise, DraftCode uses the local Codex CLI reverse proxy. Any
    execution problem returns ``None`` so agents can fall back deterministically.
    """
    if os.getenv("DRAFTCODE_LLM_DISABLED") == "1":
        return None

    base_url = os.getenv("DRAFTCODE_LLM_BASE_URL", "").strip()
    if base_url:
        return _remote_complete(prompt, schema=schema, timeout=timeout, base_url=base_url)

    if not available():
        return None

    with tempfile.TemporaryDirectory(prefix="draftcode-llm-") as tmp_dir:
        tmp_path = Path(tmp_dir)
        output_path = tmp_path / "completion.txt"
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "-c",
            'sandbox_mode="read-only"',
            "-o",
            str(output_path),
        ]

        command.append(_prompt_with_schema(prompt, schema))

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return None

        if result.returncode != 0 or not output_path.is_file():
            return None

        try:
            text = output_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None
        return text or None


def _remote_complete(
    prompt: str,
    *,
    schema: dict | None,
    timeout: int,
    base_url: str,
) -> str | None:
    payload = {
        "model": os.getenv("DRAFTCODE_LLM_MODEL", DEFAULT_MODEL),
        "messages": [
            {
                "role": "user",
                "content": _prompt_with_schema(prompt, schema),
            }
        ],
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    api_key = os.getenv("DRAFTCODE_LLM_API_KEY", "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(
        _chat_completions_url(base_url),
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except (OSError, TimeoutError, urllib.error.URLError, ValueError):
        return None

    try:
        decoded = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return None

    choices = decoded.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    message = first_choice.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    content = content.strip()
    return content or None


def _prompt_with_schema(prompt: str, schema: dict | None) -> str:
    if schema is None:
        return prompt
    # NOTE: `codex exec --output-schema` stalls for minutes in this CLI version
    # (0.142), so we steer the JSON shape via the prompt instead.
    return (
        prompt
        + "\n\nRespond with ONLY a single-line valid JSON object matching "
        "this JSON Schema (no prose, no markdown code fences):\n"
        + json.dumps(schema, ensure_ascii=False)
    )


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1/chat/completions"):
        return normalized
    return f"{normalized}/v1/chat/completions"
