from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from draftcode import llm_client

VERDICTS = {"market_hype", "talent_undervalued", "true_split"}

DIVERGENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "verdict",
        "adjusted_market_weight",
        "confidence",
        "reasoning",
    ],
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["market_hype", "talent_undervalued", "true_split"],
        },
        "adjusted_market_weight": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "reasoning": {
            "type": "string",
            "minLength": 1,
        },
    },
}


def reason_divergence(
    name: str,
    position: str,
    talent_profile: Mapping[str, Any],
    talent_rank: int,
    market_rank: float,
    divergence: int,
    notes: str,
) -> dict[str, Any] | None:
    """Ask gpt-5.5 to classify a large talent-vs-market split.

    Any transport, parsing, or schema validation problem returns ``None`` so the
    official normalizer can fall back to its existing deterministic rule path.
    """
    payload = {
        "name": name,
        "position": position,
        "talent_profile": dict(talent_profile),
        "talent_rank": talent_rank,
        "market_rank": market_rank,
        "divergence": divergence,
        "notes": notes,
    }
    response = llm_client.complete(_prompt(payload), schema=DIVERGENCE_SCHEMA)
    if response is None:
        return None
    return _parse_response(response)


def _prompt(payload: Mapping[str, Any]) -> str:
    return (
        "You are a senior NBA draft analyst resolving a large disagreement between "
        "a structured talent model and the public market board.\n"
        "\n"
        "Classify the split with exactly one verdict:\n"
        "- market_hype: the market rank is probably too optimistic; keep the model "
        "conservative.\n"
        "- talent_undervalued: the market is capturing context the talent score misses "
        "(for example injury-driven score suppression, role context, or healthy upside); "
        "raise market weight.\n"
        "- true_split: both signals are credible and should be balanced.\n"
        "\n"
        "Set adjusted_market_weight as the market-signal weight in a two-signal fusion "
        "score: weight * market_signal + (1 - weight) * talent_signal.\n"
        "\n"
        "Player input JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def _parse_response(response: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(_json_object_text(response))
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None

    verdict = parsed.get("verdict")
    if verdict not in VERDICTS:
        return None

    market_weight = _number_in_unit_interval(parsed.get("adjusted_market_weight"))
    confidence = _number_in_unit_interval(parsed.get("confidence"))
    reasoning = parsed.get("reasoning")
    if market_weight is None or confidence is None or not isinstance(reasoning, str):
        return None
    reasoning = reasoning.strip()
    if not reasoning:
        return None

    return {
        "verdict": verdict,
        "adjusted_market_weight": market_weight,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def _json_object_text(response: str) -> str:
    text = response.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + 1]


def _number_in_unit_interval(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0.0 or number > 1.0:
        return None
    return number


# --------------------------------------------------------------------------- #
# Axis-2 divergence: expert/mock consensus vs money/odds (creative point 1, v3).
# --------------------------------------------------------------------------- #
ODDS_VERDICTS = {"odds_sharp", "mock_lagging", "true_split"}

ODDS_DIVERGENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["verdict", "confidence", "reasoning"],
    "properties": {
        "verdict": {"type": "string", "enum": ["odds_sharp", "mock_lagging", "true_split"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reasoning": {"type": "string", "minLength": 1},
    },
}


def reason_odds_divergence(
    name: str,
    position: str,
    market_rank: float,
    odds_rank: float,
    divergence: int,
    notes: str,
) -> dict[str, Any] | None:
    """Ask gpt-5.5 to adjudicate an expert(mock)-vs-money(odds) split.

    Money usually leads expert consensus (it reacts to insider news faster), so
    a large split is a candidate alpha signal. Any transport/parse problem -> None
    so the caller falls back to the deterministic rule label.
    """
    payload = {
        "name": name,
        "position": position,
        "mock_consensus_rank": market_rank,
        "odds_implied_rank": odds_rank,
        "divergence": divergence,
        "notes": notes,
    }
    response = llm_client.complete(_odds_prompt(payload), schema=ODDS_DIVERGENCE_SCHEMA)
    if response is None:
        return None
    return _parse_odds_response(response)


def _odds_prompt(payload: Mapping[str, Any]) -> str:
    return (
        "You are a senior NBA draft analyst resolving a disagreement between the "
        "public mock-draft consensus (expert opinion) and the sportsbook odds "
        "(real money). Money typically reacts to insider news faster than mocks.\n"
        "\n"
        "Classify the split with exactly one verdict:\n"
        "- odds_sharp: the money is ahead of the mocks (likely insider/late info); "
        "trust the odds-implied landing.\n"
        "- mock_lagging: similar, but specifically the mock consensus is stale and "
        "hasn't caught up to the market.\n"
        "- true_split: both signals are credible and should be balanced.\n"
        "\n"
        "Player input JSON:\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def _parse_odds_response(response: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(_json_object_text(response))
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    verdict = parsed.get("verdict")
    if verdict not in ODDS_VERDICTS:
        return None
    confidence = _number_in_unit_interval(parsed.get("confidence"))
    reasoning = parsed.get("reasoning")
    if confidence is None or not isinstance(reasoning, str) or not reasoning.strip():
        return None
    return {"verdict": verdict, "confidence": confidence, "reasoning": reasoning.strip()}
