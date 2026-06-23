from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from typing import Any

from draftcode import llm_client

GM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "adjustments": {
            "type": "object",
            "description": "Map prospect_id to a small preference delta in [-0.08, 0.08].",
            "additionalProperties": {"type": "number", "minimum": -0.08, "maximum": 0.08},
        },
        "ranking": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "prospect_id": {"type": "string"},
                    "delta": {"type": "number", "minimum": -0.08, "maximum": 0.08},
                    "reason": {"type": "string"},
                },
                "required": ["prospect_id", "delta", "reason"],
            },
        },
        "rationale": {"type": "string"},
    },
    "required": ["adjustments", "ranking", "rationale"],
}

EXPLANATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"text": {"type": "string"}},
    "required": ["text"],
}

REDTEAM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "questions": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 8,
        }
    },
    "required": ["questions"],
}


def gm_agent(
    dossier: Any,
    candidates: Sequence[Any],
    *,
    use_llm: bool = True,
    timeout: int = 180,
) -> dict[str, Any]:
    """Return LLM GM preference deltas for one team, or an empty fallback."""
    if not use_llm:
        return _gm_fallback(dossier)

    payload = {
        "team_dossier": _to_plain(dossier),
        "candidates": [_candidate_payload(candidate) for candidate in candidates],
    }
    prompt = (
        "You are DraftCode's NBA draft war-room GM agent. Use the team dossier "
        "to make small candidate preference adjustments. Stay conservative: deltas "
        "must be between -0.08 and 0.08, and only adjust candidates where the dossier "
        "clearly changes the deterministic board. Return JSON only.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    raw = llm_client.complete(prompt, schema=GM_SCHEMA, timeout=timeout)
    parsed = _loads_json_object(raw)
    if parsed is None:
        return _gm_fallback(dossier)
    normalized = _normalize_gm_response(dossier, candidates, parsed)
    if normalized is None:
        return _gm_fallback(dossier)
    normalized["used_llm"] = True
    return normalized


def explanation_agent(
    pick_record: Mapping[str, Any],
    *,
    use_llm: bool = True,
    timeout: int = 180,
) -> str:
    """Return a concise war-room explanation for one pick."""
    return explanation_agent_result(pick_record, use_llm=use_llm, timeout=timeout)["text"]


def explanation_agent_result(
    pick_record: Mapping[str, Any],
    *,
    use_llm: bool = True,
    timeout: int = 180,
) -> dict[str, Any]:
    if not use_llm:
        return {"used_llm": False, "text": _fallback_explanation(pick_record)}

    prompt = (
        "You are DraftCode's draft-night explanation agent. Write one compact "
        "war-room note in Chinese. Explain why this team selected this prospect, "
        "grounding the note in the trace signals and confidence fields. Do not invent "
        "injury or private workout information. Return JSON only.\n\n"
        f"{json.dumps(_to_plain(pick_record), ensure_ascii=False, indent=2)}"
    )
    raw = llm_client.complete(prompt, schema=EXPLANATION_SCHEMA, timeout=timeout)
    parsed = _loads_json_object(raw)
    text = "" if parsed is None else str(parsed.get("text", "")).strip()
    if not text:
        return {"used_llm": False, "text": _fallback_explanation(pick_record)}
    return {"used_llm": True, "text": text}


def redteam_agent(
    board_summary: Mapping[str, Any],
    milestones: Sequence[Any],
    *,
    use_llm: bool = True,
    timeout: int = 180,
) -> list[str]:
    """Return red-team challenges for the board and milestone output."""
    return redteam_agent_result(
        board_summary,
        milestones,
        use_llm=use_llm,
        timeout=timeout,
    )["questions"]


def redteam_agent_result(
    board_summary: Mapping[str, Any],
    milestones: Sequence[Any],
    *,
    use_llm: bool = True,
    timeout: int = 180,
) -> dict[str, Any]:
    if not use_llm:
        return {
            "used_llm": False,
            "questions": _fallback_redteam(board_summary, milestones),
        }

    payload = {
        "board_summary": _to_plain(board_summary),
        "milestones": [_to_plain(milestone) for milestone in milestones],
    }
    prompt = (
        "You are DraftCode's red-team agent. Challenge this NBA draft prediction "
        "board. Look for overfitting, groupthink, low-confidence picks, ignored "
        "medical/measurement risk, and extreme milestone assumptions. Return concise "
        "Chinese questions as JSON only.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    raw = llm_client.complete(prompt, schema=REDTEAM_SCHEMA, timeout=timeout)
    parsed = _loads_json_object(raw)
    questions = _normalize_questions(None if parsed is None else parsed.get("questions"))
    if not questions:
        return {
            "used_llm": False,
            "questions": _fallback_redteam(board_summary, milestones),
        }
    return {"used_llm": True, "questions": questions}


def _gm_fallback(dossier: Any) -> dict[str, Any]:
    plain = _to_plain(dossier)
    return {
        "team": str(plain.get("team", "")),
        "abbreviation": str(plain.get("abbreviation", "")),
        "used_llm": False,
        "adjustments": {},
        "ranking": [],
        "rationale": "LLM unavailable; using deterministic dossier preference only.",
    }


def _normalize_gm_response(
    dossier: Any,
    candidates: Sequence[Any],
    parsed: Mapping[str, Any],
) -> dict[str, Any] | None:
    plain = _to_plain(dossier)
    candidate_ids = {
        str(payload["prospect_id"])
        for payload in (_candidate_payload(candidate) for candidate in candidates)
        if payload.get("prospect_id")
    }
    if not candidate_ids:
        return None

    adjustments: dict[str, float] = {}
    raw_adjustments = parsed.get("adjustments", {})
    if isinstance(raw_adjustments, Mapping):
        for prospect_id, delta in raw_adjustments.items():
            normalized_id = str(prospect_id)
            if normalized_id in candidate_ids:
                adjustments[normalized_id] = round(_bounded_float(delta, -0.08, 0.08), 4)

    ranking: list[dict[str, Any]] = []
    raw_ranking = parsed.get("ranking", [])
    if isinstance(raw_ranking, Sequence) and not isinstance(raw_ranking, str):
        seen: set[str] = set()
        for row in raw_ranking:
            if not isinstance(row, Mapping):
                continue
            prospect_id = str(row.get("prospect_id", "")).strip()
            if prospect_id not in candidate_ids or prospect_id in seen:
                continue
            delta = _bounded_float(row.get("delta", adjustments.get(prospect_id, 0.0)), -0.08, 0.08)
            reason = str(row.get("reason", "")).strip()
            adjustments.setdefault(prospect_id, round(delta, 4))
            ranking.append(
                {
                    "prospect_id": prospect_id,
                    "delta": round(delta, 4),
                    "reason": reason[:240],
                }
            )
            seen.add(prospect_id)

    if not ranking and adjustments:
        ranking = [
            {"prospect_id": prospect_id, "delta": delta, "reason": ""}
            for prospect_id, delta in sorted(
                adjustments.items(),
                key=lambda item: (-abs(item[1]), item[0]),
            )
        ]

    return {
        "team": str(plain.get("team", "")),
        "abbreviation": str(plain.get("abbreviation", "")),
        "used_llm": False,
        "adjustments": dict(sorted(adjustments.items())),
        "ranking": ranking,
        "rationale": str(parsed.get("rationale", "")).strip()[:500],
    }


def _fallback_explanation(pick_record: Mapping[str, Any]) -> str:
    team = str(pick_record.get("abbreviation") or pick_record.get("team") or "Team")
    prospect = str(
        pick_record.get("prospect_name")
        or pick_record.get("selected")
        or pick_record.get("prospect")
        or "the selected prospect"
    )
    pick = pick_record.get("pick", "")
    probability = _optional_float(pick_record.get("marginal_probability"))
    if probability is None:
        probability = _optional_float(pick_record.get("leader_probability"))

    selected_trace = _selected_trace_row(pick_record)
    preference = selected_trace.get("preference", {}) if selected_trace else {}
    signal_text = _preference_signal_text(preference)
    confidence_text = ""
    if probability is not None:
        confidence_text = f"marginal={probability:.2f}"
    if pick_record.get("low_confidence"):
        confidence_text = (
            f"{confidence_text}; low-confidence branch"
            if confidence_text
            else "low-confidence branch"
        )
    detail_text = f"; {confidence_text}" if confidence_text else ""

    if signal_text:
        return (
            f"作战室记录: pick {pick} {team} 选择 {prospect}, "
            f"核心信号为 {signal_text}{detail_text}."
        )
    return (
        f"作战室记录: pick {pick} {team} 选择 {prospect}, "
        f"沿用确定性棋盘与球队档案偏好{detail_text}."
    )


def _fallback_redteam(
    board_summary: Mapping[str, Any],
    milestones: Sequence[Any],
) -> list[str]:
    questions: list[str] = []
    low_confidence = board_summary.get("low_confidence_picks", [])
    if isinstance(low_confidence, Sequence) and not isinstance(low_confidence, str):
        for pick in list(low_confidence)[:5]:
            questions.append(f"Pick {pick} is low confidence: what alternative board branch wins?")

    for milestone in milestones:
        row = _to_plain(milestone)
        question_id = str(row.get("id", "milestone"))
        answer_kind = str(row.get("answer_kind", ""))
        expected = _optional_float(row.get("expected"))
        p10 = _optional_float(row.get("p10"))
        p90 = _optional_float(row.get("p90"))
        confidence = _optional_float(row.get("confidence"))
        if answer_kind == "category" and confidence is not None and confidence < 0.5:
            questions.append(
                f"{question_id} has a weak category mode: is the school answer stable?"
            )
        if expected is not None and (expected <= 0.2 or expected >= 24):
            questions.append(
                f"{question_id} is extreme at expected={expected:.1f}: verify input coverage."
            )
        if p10 is not None and p90 is not None and p90 - p10 >= 5:
            questions.append(
                f"{question_id} has a wide P10-P90 band: expose the driver before locking it."
            )

    if not questions:
        questions.append(
            "Check whether dossier preferences are reinforcing consensus board groupthink."
        )
    return questions[:8]


def _selected_trace_row(pick_record: Mapping[str, Any]) -> Mapping[str, Any]:
    trace = pick_record.get("trace", {})
    selected_id = str(pick_record.get("prospect_id", ""))
    selected_name = str(pick_record.get("prospect_name", ""))
    if isinstance(trace, Mapping):
        candidates = trace.get("top_candidates", [])
        if isinstance(candidates, Sequence) and not isinstance(candidates, str):
            for row in candidates:
                if not isinstance(row, Mapping):
                    continue
                if selected_id and str(row.get("prospect_id", "")) == selected_id:
                    return row
                if selected_name and str(row.get("prospect", "")) == selected_name:
                    return row
            if candidates and isinstance(candidates[0], Mapping):
                return candidates[0]
    return {}


def _preference_signal_text(preference: Any) -> str:
    if not isinstance(preference, Mapping):
        return ""
    labels = [
        ("talent", "talent"),
        ("need_fit", "need"),
        ("persona_fit", "persona"),
        ("market", "market"),
        ("llm_delta", "llm_delta"),
    ]
    parts = []
    for key, label in labels:
        value = _optional_float(preference.get(key))
        if value is not None:
            parts.append(f"{label}={value:.2f}")
    return ", ".join(parts)


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    row = _to_plain(candidate)
    return {
        "prospect_id": row.get("prospect_id"),
        "name": row.get("name"),
        "position": row.get("primary_position"),
        "archetype": row.get("archetype"),
        "consensus_rank": row.get("consensus_rank"),
        "talent_composite": row.get("talent_composite"),
        "espn_rank": row.get("espn_rank"),
        "model_pick_low": row.get("model_pick_low"),
        "talent_rank": row.get("talent_rank"),
        "market_rank": row.get("market_rank"),
        "talent_signal": row.get("talent_signal"),
        "market_signal": row.get("market_signal"),
        "fused_score": row.get("fused_score"),
        "notes": row.get("notes", ""),
    }


def _to_plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _to_plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(child) for child in value]
    return value


def _loads_json_object(text: str | None) -> dict[str, Any] | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_questions(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return []
    questions = [str(item).strip() for item in value if str(item).strip()]
    return questions[:8]


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_float(value: Any, lower: float, upper: float) -> float:
    numeric = _optional_float(value)
    if numeric is None:
        return 0.0
    return max(lower, min(upper, numeric))
