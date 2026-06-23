from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_TIMELINES = frozenset({"rebuild", "play-in", "contend"})
VALID_PHILOSOPHIES = frozenset({"BPA", "NEED", "balanced"})
VALID_RISK_TOLERANCE = frozenset({"low", "med", "high"})
POSITIONS = ("G", "W", "B")


@dataclass(frozen=True)
class GMPersona:
    philosophy: str
    archetype_pref: tuple[str, ...]
    risk_tolerance: str
    intl_openness: float
    notes: str


@dataclass(frozen=True)
class TeamDossier:
    team: str
    abbreviation: str
    timeline: str
    roster_needs: dict[str, float]
    gm_persona: GMPersona


def load_team_dossiers(path: Path) -> dict[str, TeamDossier]:
    """Load team dossiers from JSON and index them by team abbreviation."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = raw.get("teams", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        raise ValueError("team_dossiers.json must contain a list or a {'teams': [...]} object")

    dossiers: dict[str, TeamDossier] = {}
    for row in rows:
        dossier = _parse_dossier(row)
        if dossier.abbreviation in dossiers:
            raise ValueError(f"Duplicate team dossier: {dossier.abbreviation}")
        dossiers[dossier.abbreviation] = dossier
    return dict(sorted(dossiers.items()))


def _parse_dossier(row: Any) -> TeamDossier:
    if not isinstance(row, dict):
        raise ValueError("Each team dossier must be an object")

    team = _required_str(row, "team")
    abbreviation = _required_str(row, "abbreviation")
    timeline = _required_str(row, "timeline")
    if timeline not in VALID_TIMELINES:
        raise ValueError(f"{abbreviation}: invalid timeline {timeline!r}")

    raw_needs = row.get("roster_needs")
    if not isinstance(raw_needs, dict):
        raise ValueError(f"{abbreviation}: roster_needs must be an object")
    roster_needs = {
        position: _bounded_float(raw_needs.get(position), position)
        for position in POSITIONS
    }

    raw_persona = row.get("gm_persona")
    if not isinstance(raw_persona, dict):
        raise ValueError(f"{abbreviation}: gm_persona must be an object")
    philosophy = _required_str(raw_persona, "philosophy")
    if philosophy not in VALID_PHILOSOPHIES:
        raise ValueError(f"{abbreviation}: invalid philosophy {philosophy!r}")
    risk_tolerance = _required_str(raw_persona, "risk_tolerance")
    if risk_tolerance not in VALID_RISK_TOLERANCE:
        raise ValueError(f"{abbreviation}: invalid risk_tolerance {risk_tolerance!r}")
    archetype_pref = raw_persona.get("archetype_pref")
    if not isinstance(archetype_pref, list) or not archetype_pref:
        raise ValueError(f"{abbreviation}: archetype_pref must be a non-empty list")

    persona = GMPersona(
        philosophy=philosophy,
        archetype_pref=tuple(
            str(value).strip().lower()
            for value in archetype_pref
            if str(value).strip()
        ),
        risk_tolerance=risk_tolerance,
        intl_openness=_bounded_float(raw_persona.get("intl_openness"), "intl_openness"),
        notes=_required_str(raw_persona, "notes"),
    )
    if not persona.archetype_pref:
        raise ValueError(f"{abbreviation}: archetype_pref must include at least one value")

    return TeamDossier(
        team=team,
        abbreviation=abbreviation,
        timeline=timeline,
        roster_needs=roster_needs,
        gm_persona=persona,
    )


def _required_str(row: dict[str, Any], field_name: str) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing required string field: {field_name}")
    return value.strip()


def _bounded_float(value: Any, field_name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}") from exc
    if not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be between 0 and 1")
    return numeric
