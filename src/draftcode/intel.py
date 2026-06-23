from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from draftcode import llm_client


@dataclass(frozen=True)
class PickMove:
    pick_number: int
    from_team: str
    to_team: str


@dataclass(frozen=True)
class NeedsDelta:
    team: str
    new_timeline: str
    position_focus: str


@dataclass(frozen=True)
class IntelReport:
    picks_moved: list[PickMove]
    needs_delta: list[NeedsDelta]
    affects_draft_order: bool
    raw_excerpt: str
    source: str


NBA_TEAMS: dict[str, str] = {
    "ATL": "Atlanta Hawks",
    "BOS": "Boston Celtics",
    "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets",
    "CHI": "Chicago Bulls",
    "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks",
    "DEN": "Denver Nuggets",
    "DET": "Detroit Pistons",
    "GSW": "Golden State Warriors",
    "HOU": "Houston Rockets",
    "IND": "Indiana Pacers",
    "LAC": "Los Angeles Clippers",
    "LAL": "Los Angeles Lakers",
    "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat",
    "MIL": "Milwaukee Bucks",
    "MIN": "Minnesota Timberwolves",
    "NOP": "New Orleans Pelicans",
    "NYK": "New York Knicks",
    "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic",
    "PHI": "Philadelphia 76ers",
    "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers",
    "SAC": "Sacramento Kings",
    "SAS": "San Antonio Spurs",
    "TOR": "Toronto Raptors",
    "UTA": "Utah Jazz",
    "WAS": "Washington Wizards",
}

TEAM_ABBREVIATIONS: dict[str, str] = {team: abbr for abbr, team in NBA_TEAMS.items()}
_DRAFT_ORDER_COLUMNS = ["pick", "team", "abbreviation", "original_team", "via_trade"]
_TEAM_NEEDS_COLUMNS = [
    "abbreviation",
    "position",
    "weight",
    "timeline",
    "intel_focus",
    "intel_source",
]


def extract_intel(news_text: str, draft_order: Sequence[object], source: str = "") -> IntelReport:
    """Extract draft-order intelligence from externally supplied news text."""
    excerpt = _excerpt(news_text)
    if not news_text.strip():
        return _empty_report(raw_excerpt=excerpt, source=source)

    response = llm_client.complete(
        _build_prompt(news_text, draft_order, source),
        schema=_INTEL_SCHEMA,
        timeout=180,
    )
    if response is None:
        return _empty_report(raw_excerpt=excerpt, source=source)

    payload = _parse_json_object(response)
    if payload is None:
        return _empty_report(raw_excerpt=excerpt, source=source)

    try:
        picks_moved = _parse_pick_moves(payload)
        needs_delta = _parse_needs_delta(payload)
    except (KeyError, TypeError, ValueError):
        return _empty_report(raw_excerpt=excerpt, source=source)

    return IntelReport(
        picks_moved=picks_moved,
        needs_delta=needs_delta,
        affects_draft_order=bool(payload.get("affects_our_draft_order")) or bool(picks_moved),
        raw_excerpt=excerpt,
        source=source,
    )


def apply_intel(report: IntelReport, data_dir: Path, *, dry_run: bool = True) -> dict[str, Any]:
    """Apply extracted pick moves and team-need changes, with an audit trace."""
    draft_order_path = data_dir / "draft_order.csv"
    team_needs_path = data_dir / "team_needs.csv"
    draft_fields, draft_rows = _read_csv_with_fields(draft_order_path)
    need_fields, need_rows = _read_optional_csv_with_fields(team_needs_path)

    draft_changes = _preview_draft_order_changes(report, draft_rows)
    needs_changes = _preview_needs_changes(report, need_rows)

    if not dry_run:
        _write_csv(
            draft_order_path,
            _merged_fields(draft_fields, _DRAFT_ORDER_COLUMNS),
            draft_rows,
        )
        _write_csv(
            team_needs_path,
            _merged_fields(need_fields, _TEAM_NEEDS_COLUMNS),
            need_rows,
        )

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "affects_draft_order": report.affects_draft_order,
        "draft_order_changes": draft_changes,
        "needs_changes": needs_changes,
    }
    audit_path = _write_audit(report, result)
    result["audit_path"] = str(audit_path)
    return result


def resolve_team_abbreviation(value: str) -> str | None:
    """Resolve a full name, abbreviation, nickname, city, or clear partial to an NBA code."""
    key = _team_key(value)
    if not key:
        return None
    aliases = _team_aliases()
    if key in aliases:
        return aliases[key]

    matches = {
        abbr
        for alias, abbr in aliases.items()
        if len(key) >= 4 and (key in alias or alias in key)
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


def team_full_name(value: str) -> str:
    abbr = resolve_team_abbreviation(value)
    if abbr is None:
        return value.strip()
    return NBA_TEAMS[abbr]


def _build_prompt(news_text: str, draft_order: Sequence[object], source: str) -> str:
    order_rows = [_draft_order_context(row) for row in draft_order]
    return (
        "You are DraftCode's real-time NBA draft intelligence extraction agent. "
        "The fetch layer is external; only structure this supplied text. "
        "Identify 2026 first-round pick ownership changes and team-need deltas that "
        "matter to the current draft order. Return no speculation.\n\n"
        f"Source: {source or 'unspecified'}\n"
        f"Current draft order JSON: {json.dumps(order_rows, ensure_ascii=False)}\n\n"
        "News text:\n"
        f"{news_text.strip()}\n\n"
        "Use these keys exactly: picks_moved_2026_round1, team_needs_delta, "
        "affects_our_draft_order. If no concrete pick move is present, return empty arrays."
    )


def _draft_order_context(row: object) -> dict[str, object]:
    if isinstance(row, Mapping):
        return {
            "pick": row.get("pick"),
            "team": row.get("team"),
            "abbreviation": row.get("abbreviation"),
        }
    return {
        "pick": getattr(row, "pick", None),
        "team": getattr(row, "team", None),
        "abbreviation": getattr(row, "abbreviation", None),
    }


def _parse_pick_moves(payload: Mapping[str, Any]) -> list[PickMove]:
    raw_moves = payload.get("picks_moved_2026_round1", payload.get("picks_moved", []))
    if not isinstance(raw_moves, list):
        raise TypeError("picks_moved_2026_round1 must be a list")

    moves: list[PickMove] = []
    for raw in raw_moves:
        if not isinstance(raw, Mapping):
            raise TypeError("pick move must be an object")
        pick_number = int(raw["pick_number"])
        from_team = _normalize_team_reference(str(raw.get("from_team", "")))
        to_team = _normalize_team_reference(str(raw.get("to_team", "")))
        if from_team and to_team:
            moves.append(
                PickMove(
                    pick_number=pick_number,
                    from_team=from_team,
                    to_team=to_team,
                )
            )
    return moves


def _parse_needs_delta(payload: Mapping[str, Any]) -> list[NeedsDelta]:
    raw_deltas = payload.get("team_needs_delta", payload.get("needs_delta", []))
    if not isinstance(raw_deltas, list):
        raise TypeError("team_needs_delta must be a list")

    deltas: list[NeedsDelta] = []
    for raw in raw_deltas:
        if not isinstance(raw, Mapping):
            raise TypeError("team need delta must be an object")
        team = _normalize_team_reference(str(raw.get("team", "")))
        if not team:
            continue
        deltas.append(
            NeedsDelta(
                team=team,
                new_timeline=str(raw.get("new_timeline", "")).strip(),
                position_focus=str(raw.get("position_focus", "")).strip(),
            )
        )
    return deltas


def _normalize_team_reference(value: str) -> str:
    abbr = resolve_team_abbreviation(value)
    return abbr or value.strip()


def _preview_draft_order_changes(
    report: IntelReport,
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    rows_by_pick = {_safe_int(row.get("pick")): row for row in rows}

    for move in report.picks_moved:
        row = rows_by_pick.get(move.pick_number)
        to_abbr = resolve_team_abbreviation(move.to_team)
        from_abbr = resolve_team_abbreviation(move.from_team)
        if row is None:
            changes.append(
                {
                    "pick": move.pick_number,
                    "from": move.from_team,
                    "to": move.to_team,
                    "status": "missing_pick",
                }
            )
            continue
        if to_abbr is None:
            changes.append(
                {
                    "pick": move.pick_number,
                    "from": move.from_team,
                    "to": move.to_team,
                    "status": "unknown_to_team",
                }
            )
            continue

        current_abbr = row.get("abbreviation", "").strip()
        current_team = row.get("team", "").strip()
        original_team = row.get("original_team", "").strip() or current_abbr
        status = "already_current" if current_abbr == to_abbr else "updated"
        change = {
            "pick": move.pick_number,
            "from": from_abbr or move.from_team,
            "to": to_abbr,
            "current_team": current_team,
            "current_abbreviation": current_abbr,
            "new_team": NBA_TEAMS[to_abbr],
            "new_abbreviation": to_abbr,
            "original_team": original_team,
            "via_trade": True,
            "status": status,
        }
        if from_abbr and current_abbr and current_abbr != from_abbr and current_abbr != to_abbr:
            change["warning"] = f"current owner is {current_abbr}, not reported {from_abbr}"
        changes.append(change)

        if status == "updated":
            row["team"] = NBA_TEAMS[to_abbr]
            row["abbreviation"] = to_abbr
            row["original_team"] = original_team
            row["via_trade"] = "true"
        elif row.get("via_trade", "").strip().lower() == "true":
            row["original_team"] = original_team
            row["via_trade"] = "true"

    return changes


def _preview_needs_changes(
    report: IntelReport,
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    index = {
        (row.get("abbreviation", "").strip(), row.get("position", "").strip()): row
        for row in rows
    }

    for delta in report.needs_delta:
        abbr = resolve_team_abbreviation(delta.team)
        if abbr is None:
            changes.append(
                {
                    "team": delta.team,
                    "position": "",
                    "status": "unknown_team",
                    "timeline": delta.new_timeline,
                    "focus": delta.position_focus,
                }
            )
            continue

        positions = _positions_from_focus(delta.position_focus)
        if not positions:
            positions = ["W"]

        for position in positions:
            key = (abbr, position)
            row = index.get(key)
            before = _safe_float(row.get("weight")) if row is not None else None
            after = max(before if before is not None else 0.0, 0.85)
            status = "updated" if row is not None else "inserted"
            if row is None:
                row = {
                    "abbreviation": abbr,
                    "position": position,
                    "weight": _format_float(after),
                }
                rows.append(row)
                index[key] = row
            else:
                row["weight"] = _format_float(after)
            row["timeline"] = delta.new_timeline
            row["intel_focus"] = delta.position_focus
            row["intel_source"] = report.source
            changes.append(
                {
                    "team": abbr,
                    "position": position,
                    "before_weight": before,
                    "after_weight": after,
                    "timeline": delta.new_timeline,
                    "focus": delta.position_focus,
                    "status": status,
                }
            )

    return changes


def _positions_from_focus(focus: str) -> list[str]:
    key = focus.lower()
    positions: list[str] = []
    if any(term in key for term in ["guard", "point", "shooting", "backcourt", "pg", "sg"]):
        positions.append("G")
    if any(term in key for term in ["wing", "forward", "upside", "sf", "pf"]):
        positions.append("W")
    if any(term in key for term in ["big", "center", "centre", "frontcourt", "rim"]):
        positions.append("B")
    return list(dict.fromkeys(positions))


def _read_csv_with_fields(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Required data file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _read_optional_csv_with_fields(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    return _read_csv_with_fields(path)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_audit(report: IntelReport, result: Mapping[str, Any]) -> Path:
    audit_dir = Path("outputs/intel")
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"intel_{_next_audit_sequence(audit_dir):03d}.json"
    payload = {
        "report": asdict(report),
        "application": dict(result),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _next_audit_sequence(audit_dir: Path) -> int:
    highest = 0
    for path in audit_dir.glob("intel_*.json"):
        match = re.fullmatch(r"intel_(\d+)\.json", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _merged_fields(existing: list[str], required: list[str]) -> list[str]:
    merged = list(existing)
    for field in required:
        if field not in merged:
            merged.append(field)
    return merged or list(required)


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        payload = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _empty_report(raw_excerpt: str, source: str) -> IntelReport:
    return IntelReport(
        picks_moved=[],
        needs_delta=[],
        affects_draft_order=False,
        raw_excerpt=raw_excerpt,
        source=source,
    )


def _excerpt(news_text: str, limit: int = 1200) -> str:
    normalized = " ".join(news_text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _safe_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _safe_float(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _format_float(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _team_key(value: str) -> str:
    lowered = value.strip().lower().replace("&", " and ")
    lowered = lowered.replace(".", "")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _team_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    city_counts: dict[str, int] = {}
    city_by_abbr: dict[str, str] = {}
    for abbr, full_name in NBA_TEAMS.items():
        words = full_name.split()
        nickname = " ".join(words[1:])
        if full_name.startswith("Portland Trail"):
            city = "Portland"
            nickname = "Trail Blazers"
        elif full_name.startswith("Golden State"):
            city = "Golden State"
            nickname = "Warriors"
        elif full_name.startswith("Los Angeles"):
            city = "Los Angeles"
            nickname = words[-1]
        elif full_name.startswith("New Orleans"):
            city = "New Orleans"
            nickname = "Pelicans"
        elif full_name.startswith("New York"):
            city = "New York"
            nickname = "Knicks"
        elif full_name.startswith("Oklahoma City"):
            city = "Oklahoma City"
            nickname = "Thunder"
        else:
            city = words[0]
            nickname = " ".join(words[1:])
        city_key = _team_key(city)
        city_counts[city_key] = city_counts.get(city_key, 0) + 1
        city_by_abbr[abbr] = city
        for alias in {abbr, full_name, nickname}:
            aliases[_team_key(alias)] = abbr

    for abbr, city in city_by_abbr.items():
        key = _team_key(city)
        if city_counts.get(key) == 1:
            aliases[key] = abbr

    aliases.update(
        {
            "la clippers": "LAC",
            "clips": "LAC",
            "la lakers": "LAL",
            "sixers": "PHI",
            "76ers": "PHI",
            "suns": "PHX",
            "phoenix": "PHX",
            "blazers": "POR",
            "trail blazers": "POR",
            "gs warriors": "GSW",
            "dubs": "GSW",
            "okc": "OKC",
            "brooklyn": "BKN",
            "nets": "BKN",
            "new orleans": "NOP",
            "pelicans": "NOP",
        }
    )
    return aliases


_INTEL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "picks_moved_2026_round1": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pick_number": {"type": "integer"},
                    "from_team": {"type": "string"},
                    "to_team": {"type": "string"},
                },
                "required": ["pick_number", "from_team", "to_team"],
            },
        },
        "team_needs_delta": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "team": {"type": "string"},
                    "new_timeline": {"type": "string"},
                    "position_focus": {"type": "string"},
                },
                "required": ["team", "new_timeline", "position_focus"],
            },
        },
        "affects_our_draft_order": {"type": "boolean"},
    },
    "required": [
        "picks_moved_2026_round1",
        "team_needs_delta",
        "affects_our_draft_order",
    ],
}
