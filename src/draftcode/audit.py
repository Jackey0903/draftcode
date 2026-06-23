from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def build_audit(twin_path: Path, llm_dir: Path, data_dir: Path) -> dict[str, Any]:
    """Join Draft Twin outputs, LLM cache artifacts, and source data into one audit."""
    if not twin_path.is_file():
        raise FileNotFoundError(f"Required Draft Twin artifact is missing: {twin_path}")

    twin = json.loads(twin_path.read_text(encoding="utf-8"))
    explanations_path = llm_dir / "explanations.json"
    redteam_path = llm_dir / "redteam.json"
    gm_preferences_path = llm_dir / "gm_preferences.json"
    prospects_path = data_dir / "prospects.csv"

    explanations_payload = _read_optional_json(explanations_path)
    redteam_payload = _read_optional_json(redteam_path)
    gm_preferences_payload = _read_optional_json(gm_preferences_path)
    prospects_payload = _read_optional_prospects(prospects_path)

    explanation_index = _build_explanation_index(explanations_payload)
    gm_preferences = _build_gm_index(gm_preferences_payload)
    divergence_index = prospects_payload if prospects_payload is not None else {}

    pick_index = _index_by_pick(twin.get("picks", []))
    low_confidence_picks = _int_set(twin.get("low_confidence_picks", []))
    audit_picks: list[dict[str, Any]] = []

    for assigned in sorted(_mapping_rows(twin.get("assigned_picks", [])), key=_pick_sort_key):
        pick_number = _optional_int(assigned.get("pick"))
        pick_details = pick_index.get(pick_number, {})
        abbreviation = str(assigned.get("abbreviation", ""))
        prospect_id = str(assigned.get("prospect_id", ""))
        most_likely_id = _optional_str(pick_details.get("most_likely_id"))
        matches_most_likely = prospect_id == most_likely_id
        explanation = explanation_index.get((pick_number, abbreviation, prospect_id))
        divergence = divergence_index.get(prospect_id)
        gm_influence = _gm_influence(gm_preferences, abbreviation, prospect_id)
        low_confidence = bool(pick_details.get("low_confidence", False))
        if pick_number in low_confidence_picks:
            low_confidence = True

        audit_picks.append(
            {
                "pick": pick_number,
                "team": _optional_str(assigned.get("team")),
                "abbreviation": abbreviation,
                "prospect_id": prospect_id,
                "prospect_name": _optional_str(assigned.get("prospect_name")),
                "assigned_probability": _optional_float(
                    assigned.get("marginal_probability")
                ),
                "most_likely_id": most_likely_id,
                "most_likely_name": _optional_str(pick_details.get("most_likely_name")),
                "most_likely_probability": _optional_float(pick_details.get("probability")),
                "matches_most_likely": matches_most_likely,
                "low_confidence": low_confidence,
                "explanation": explanation,
                "divergence": divergence,
                "gm_influence": gm_influence,
            }
        )

    red_team = _red_team(redteam_payload)
    integrity = {
        "picks_audited": len(audit_picks),
        "picks_with_explanation": sum(
            1 for pick in audit_picks if pick["explanation"] is not None
        ),
        "picks_diverging_from_most_likely": sum(
            1 for pick in audit_picks if not pick["matches_most_likely"]
        ),
        "llm_divergence_verdicts": sum(
            1 for pick in audit_picks if pick["divergence"] is not None
        ),
        "gm_influenced_picks": sum(
            1 for pick in audit_picks if pick["gm_influence"] is not None
        ),
        "red_team_challenges": len(red_team["questions"]),
        "low_confidence_picks": sum(1 for pick in audit_picks if pick["low_confidence"]),
    }

    return {
        "schema_version": 1,
        "sources": {
            "twin": str(twin_path),
            "explanations": str(explanations_path)
            if explanations_payload is not None
            else None,
            "redteam": str(redteam_path) if redteam_payload is not None else None,
            "gm_preferences": str(gm_preferences_path)
            if gm_preferences_payload is not None
            else None,
            "prospects": str(prospects_path) if prospects_payload is not None else None,
        },
        "picks": audit_picks,
        "milestones": twin.get("milestones", []),
        "red_team": red_team,
        "integrity": integrity,
    }


def write_audit(audit: Mapping[str, Any], out_json: Path, out_md: Path) -> None:
    """Write machine-readable and demo-readable audit artifacts."""
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(_render_markdown(audit), encoding="utf-8")


def _read_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_optional_prospects(path: Path) -> dict[str, dict[str, Any]] | None:
    if not path.is_file():
        return None
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, UnicodeDecodeError, csv.Error):
        return None

    divergence: dict[str, dict[str, Any]] = {}
    for row in rows:
        prospect_id = _csv_text(row.get("prospect_id"))
        verdict = _csv_text(row.get("divergence_llm_verdict"))
        if not prospect_id or not verdict:
            continue
        divergence[prospect_id] = {
            "verdict": verdict,
            "market_weight": _optional_float(row.get("divergence_llm_market_weight")),
            "confidence": _optional_float(row.get("divergence_llm_confidence")),
            "reasoning": _csv_text(row.get("divergence_llm_reasoning")),
        }
    return divergence


def _build_explanation_index(
    payload: Mapping[str, Any] | None,
) -> dict[tuple[int | None, str, str], str]:
    if payload is None:
        return {}
    rows = payload.get("picks", [])
    explanations: dict[tuple[int | None, str, str], str] = {}
    for row in _mapping_rows(rows):
        text = _optional_str(row.get("text"))
        if text is None:
            continue
        key = (
            _optional_int(row.get("pick")),
            str(row.get("abbreviation", "")),
            str(row.get("prospect_id", "")),
        )
        explanations[key] = text
    return explanations


def _build_gm_index(
    payload: Mapping[str, Any] | None,
) -> dict[str, dict[str, dict[str, Any]]]:
    if payload is None:
        return {}
    teams = payload.get("teams", {})
    if not isinstance(teams, Mapping):
        return {}

    preferences: dict[str, dict[str, dict[str, Any]]] = {}
    for abbreviation, row in teams.items():
        if not isinstance(row, Mapping):
            continue
        adjustments = row.get("adjustments", {})
        if not isinstance(adjustments, Mapping):
            continue
        team_preferences: dict[str, dict[str, Any]] = {}
        rationale = _optional_str(row.get("rationale"))
        for prospect_id, raw_delta in adjustments.items():
            delta = _optional_float(raw_delta)
            if delta is None or delta == 0:
                continue
            team_preferences[str(prospect_id)] = {
                "delta": delta,
                "rationale": rationale,
            }
        if team_preferences:
            preferences[str(abbreviation)] = team_preferences
    return preferences


def _index_by_pick(rows: object) -> dict[int | None, Mapping[str, Any]]:
    return {
        _optional_int(row.get("pick")): row
        for row in _mapping_rows(rows)
        if _optional_int(row.get("pick")) is not None
    }


def _red_team(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {"used_llm": False, "questions": []}
    raw_questions = payload.get("questions", [])
    if not isinstance(raw_questions, list):
        raw_questions = []
    questions = [
        str(question)
        for question in raw_questions
        if isinstance(question, str) and question.strip()
    ]
    return {"used_llm": bool(payload.get("used_llm", False)), "questions": questions}


def _gm_influence(
    preferences: Mapping[str, Mapping[str, dict[str, Any]]],
    abbreviation: str,
    prospect_id: str,
) -> dict[str, Any] | None:
    return preferences.get(abbreviation, {}).get(prospect_id)


def _mapping_rows(rows: object) -> list[Mapping[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _int_set(values: object) -> set[int]:
    if not isinstance(values, list):
        return set()
    result: set[int] = set()
    for value in values:
        parsed = _optional_int(value)
        if parsed is not None:
            result.add(parsed)
    return result


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _csv_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _pick_sort_key(row: Mapping[str, Any]) -> tuple[int, str]:
    pick = _optional_int(row.get("pick"))
    return (pick if pick is not None else 10_000, str(row.get("prospect_id", "")))


def _render_markdown(audit: Mapping[str, Any]) -> str:
    integrity = audit.get("integrity", {})
    assert isinstance(integrity, Mapping)
    lines = [
        "# DraftCode Audit Trail",
        "",
        (
            "Integrity: "
            f"{integrity.get('picks_audited', 0)} picks audited; "
            f"{integrity.get('picks_with_explanation', 0)} explanations; "
            f"{integrity.get('picks_diverging_from_most_likely', 0)} assigned/leader divergences; "
            f"{integrity.get('llm_divergence_verdicts', 0)} gpt-5.5 background verdicts; "
            f"{integrity.get('gm_influenced_picks', 0)} GM-influenced picks; "
            f"{integrity.get('red_team_challenges', 0)} red-team challenges; "
            f"{integrity.get('low_confidence_picks', 0)} low-confidence picks."
        ),
        "",
        "## Per-Pick Evidence",
        "",
        (
            "| Pick | Team | Prospect | P | Conf | Δ-from-most-likely | "
            "gpt-5.5 background verdict | GM Δ |"
        ),
        "| ---: | --- | --- | ---: | --- | --- | --- | ---: |",
    ]

    for pick in _sorted_pick_audits(audit.get("picks", [])):
        divergence = pick.get("divergence")
        gm_influence = pick.get("gm_influence")
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(pick.get("pick")),
                    _md_cell(pick.get("abbreviation") or pick.get("team")),
                    _md_cell(pick.get("prospect_name")),
                    _md_cell(_format_probability(pick.get("assigned_probability"))),
                    _md_cell("low" if pick.get("low_confidence") else "ok"),
                    _md_cell(_most_likely_delta(pick)),
                    _md_cell(
                        divergence.get("verdict")
                        if isinstance(divergence, Mapping)
                        else ""
                    ),
                    _md_cell(
                        _format_delta(gm_influence.get("delta"))
                        if isinstance(gm_influence, Mapping)
                        else ""
                    ),
                ]
            )
            + " |"
        )

    lines.extend(["", "## Explanations", ""])
    explanation_count = 0
    for pick in _sorted_pick_audits(audit.get("picks", [])):
        explanation = pick.get("explanation")
        if explanation is None:
            continue
        explanation_count += 1
        lines.append(f"- Pick {pick.get('pick')}: {_md_text(explanation)}")
    if explanation_count == 0:
        lines.append("- None.")

    lines.extend(["", "## 红队质询 (Red-Team Challenges)", ""])
    red_team = audit.get("red_team", {})
    questions = red_team.get("questions", []) if isinstance(red_team, Mapping) else []
    if isinstance(questions, list) and questions:
        for index, question in enumerate(questions, start=1):
            lines.append(f"{index}. {_md_text(question)}")
    else:
        lines.append("1. None.")

    lines.extend(["", "## Milestones", ""])
    milestones = audit.get("milestones", [])
    if isinstance(milestones, list) and milestones:
        for milestone in milestones:
            lines.append(f"- {_md_text(_stable_json(milestone))}")
    elif isinstance(milestones, Mapping) and milestones:
        lines.append(f"- {_md_text(_stable_json(milestones))}")
    else:
        lines.append("- None.")

    return "\n".join(lines) + "\n"


def _sorted_pick_audits(rows: object) -> list[Mapping[str, Any]]:
    return sorted(_mapping_rows(rows), key=_pick_sort_key)


def _most_likely_delta(pick: Mapping[str, Any]) -> str:
    if pick.get("matches_most_likely"):
        return ""
    leader = pick.get("most_likely_name") or pick.get("most_likely_id") or "unknown"
    probability = _format_probability(pick.get("most_likely_probability"))
    return f"leader: {leader} ({probability})"


def _format_probability(value: object) -> str:
    number = _optional_float(value)
    return "" if number is None else f"{number:.2f}"


def _format_delta(value: object) -> str:
    number = _optional_float(value)
    return "" if number is None else f"{number:+.3f}"


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _md_cell(value: object) -> str:
    return _md_text(value).replace("\n", " ")


def _md_text(value: object) -> str:
    return str(value).replace("|", "\\|")
