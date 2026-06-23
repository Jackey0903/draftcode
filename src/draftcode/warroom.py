from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

from draftcode.agents import (
    explanation_agent_result,
    gm_agent,
    redteam_agent_result,
)
from draftcode.dossier import TeamDossier, load_team_dossiers
from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.schemas import Prospect
from draftcode.simulate import MonteCarloDraftTwin, SimulationConfig, TwinReport

DEFAULT_DATA_DIR = Path("data/processed")
DEFAULT_DOSSIER_PATH = Path("data/dossiers/team_dossiers.json")
DEFAULT_OUTPUT_DIR = Path("outputs/llm")


def run_warroom(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    dossier_path: Path = DEFAULT_DOSSIER_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    draws: int = 1000,
    seed: int = 42,
    max_workers: int = 4,
    offline: bool = False,
    gm_candidate_limit: int = 15,
) -> dict[str, Any]:
    """Run the local LLM-once war-room pipeline and write cache artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    prospects = load_prospects(data_dir)
    draft_order = load_draft_order(data_dir)
    team_needs = load_team_needs(data_dir)
    mock_signals = load_mock_signals(data_dir)
    dossiers = load_team_dossiers(dossier_path)

    candidates = _select_gm_candidates(prospects, gm_candidate_limit)
    gm_cache = _run_gm_preferences(
        dossiers=dossiers,
        candidates=candidates,
        max_workers=max_workers,
        offline=offline,
    )
    gm_path = output_dir / "gm_preferences.json"
    _write_json(gm_path, gm_cache)

    gm_preferences = load_gm_adjustments(gm_path)
    twin = MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
        config=SimulationConfig(draws=draws, seed=seed),
        dossiers=dossiers,
        gm_preferences=gm_preferences,
    )
    report = twin.run()

    explanations = _run_explanations(
        report=report,
        preference_trace=twin.preference_trace,
        max_workers=max_workers,
        offline=offline,
    )
    explanations_path = output_dir / "explanations.json"
    _write_json(explanations_path, explanations)

    redteam = _run_redteam(report, offline=offline)
    redteam_path = output_dir / "redteam.json"
    _write_json(redteam_path, redteam)

    return {
        "offline": offline,
        "paths": {
            "gm_preferences": str(gm_path),
            "explanations": str(explanations_path),
            "redteam": str(redteam_path),
        },
        "gm": _usage_summary(gm_cache["teams"].values()),
        "explanations": _usage_summary(explanations["picks"]),
        "redteam": {
            "total": 1,
            "llm": 1 if redteam["used_llm"] else 0,
            "fallback": 0 if redteam["used_llm"] else 1,
        },
        "pick_count": len(report.assigned_picks),
        "low_confidence_picks": report.low_confidence_picks,
    }


def load_gm_adjustments(path: Path) -> dict[str, dict[str, float]]:
    """Load team-prospect deltas from the persisted GM preference cache."""
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    teams = payload.get("teams", {})
    if not isinstance(teams, Mapping):
        return {}

    preferences: dict[str, dict[str, float]] = {}
    for abbreviation, row in teams.items():
        if not isinstance(row, Mapping):
            continue
        raw_adjustments = row.get("adjustments", {})
        if not isinstance(raw_adjustments, Mapping):
            continue
        adjustments: dict[str, float] = {}
        for prospect_id, delta in raw_adjustments.items():
            try:
                adjustments[str(prospect_id)] = round(max(-0.08, min(0.08, float(delta))), 4)
            except (TypeError, ValueError):
                continue
        preferences[str(abbreviation)] = dict(sorted(adjustments.items()))
    return dict(sorted(preferences.items()))


def _run_gm_preferences(
    *,
    dossiers: dict[str, TeamDossier],
    candidates: list[Prospect],
    max_workers: int,
    offline: bool,
) -> dict[str, Any]:
    teams: dict[str, dict[str, Any]] = {}
    workers = max(1, max_workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_safe_gm_agent, dossier, candidates, offline): abbreviation
            for abbreviation, dossier in sorted(dossiers.items())
        }
        for future in as_completed(futures):
            abbreviation = futures[future]
            teams[abbreviation] = future.result()

    return {
        "schema_version": 1,
        "mode": "offline" if offline else "llm-once",
        "teams": {key: teams[key] for key in sorted(teams)},
    }


def _safe_gm_agent(
    dossier: TeamDossier,
    candidates: list[Prospect],
    offline: bool,
) -> dict[str, Any]:
    try:
        return gm_agent(dossier, candidates, use_llm=not offline)
    except Exception as exc:  # noqa: BLE001 - this is an agent fallback boundary.
        fallback = gm_agent(dossier, candidates, use_llm=False)
        fallback["error"] = str(exc)
        return fallback


def _run_explanations(
    *,
    report: TwinReport,
    preference_trace: list[dict[str, object]],
    max_workers: int,
    offline: bool,
) -> dict[str, Any]:
    records = _pick_records(report, preference_trace)
    results: dict[int, dict[str, Any]] = {}
    workers = max(1, max_workers)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_safe_explanation_agent, record, offline): int(record["pick"])
            for record in records
        }
        for future in as_completed(futures):
            pick = futures[future]
            results[pick] = future.result()

    return {
        "schema_version": 1,
        "mode": "offline" if offline else "llm-once",
        "picks": [results[pick] for pick in sorted(results)],
    }


def _safe_explanation_agent(record: dict[str, Any], offline: bool) -> dict[str, Any]:
    try:
        result = explanation_agent_result(record, use_llm=not offline)
    except Exception as exc:  # noqa: BLE001 - this is an agent fallback boundary.
        result = explanation_agent_result(record, use_llm=False)
        result["error"] = str(exc)
    return {
        "pick": record["pick"],
        "team": record["team"],
        "abbreviation": record["abbreviation"],
        "prospect_id": record["prospect_id"],
        "prospect_name": record["prospect_name"],
        "used_llm": bool(result["used_llm"]),
        "text": result["text"],
    }


def _run_redteam(report: TwinReport, offline: bool) -> dict[str, Any]:
    board_summary = {
        "assigned_picks": [asdict(pick) for pick in report.assigned_picks],
        "pick_leaders": [asdict(pick) for pick in report.picks],
        "low_confidence_picks": report.low_confidence_picks,
        "board_top": [asdict(outlook) for outlook in report.board[:15]],
    }
    try:
        result = redteam_agent_result(
            board_summary,
            report.milestones,
            use_llm=not offline,
        )
    except Exception as exc:  # noqa: BLE001 - this is an agent fallback boundary.
        result = redteam_agent_result(board_summary, report.milestones, use_llm=False)
        result["error"] = str(exc)
    return {
        "schema_version": 1,
        "mode": "offline" if offline else "llm-once",
        "used_llm": bool(result["used_llm"]),
        "questions": result["questions"],
    }


def _pick_records(
    report: TwinReport,
    preference_trace: list[dict[str, object]],
) -> list[dict[str, Any]]:
    trace_index = {
        int(row["pick"]): row
        for row in preference_trace
        if isinstance(row.get("pick"), int)
    }
    records: list[dict[str, Any]] = []
    for assigned, distribution in zip(report.assigned_picks, report.picks, strict=True):
        records.append(
            {
                "pick": assigned.pick,
                "team": assigned.team,
                "abbreviation": assigned.abbreviation,
                "prospect_id": assigned.prospect_id,
                "prospect_name": assigned.prospect_name,
                "marginal_probability": assigned.marginal_probability,
                "pick_leader": distribution.most_likely_name,
                "leader_probability": distribution.probability,
                "low_confidence": distribution.low_confidence,
                "top_distribution": [asdict(candidate) for candidate in distribution.distribution],
                "trace": trace_index.get(assigned.pick, {}),
            }
        )
    return records


def _select_gm_candidates(prospects: list[Prospect], limit: int) -> list[Prospect]:
    return sorted(
        prospects,
        key=lambda prospect: (
            prospect.model_pick_low or prospect.espn_rank or prospect.consensus_rank,
            prospect.consensus_rank,
            prospect.prospect_id,
        ),
    )[:limit]


def _usage_summary(records: Any) -> dict[str, int]:
    rows = list(records)
    llm_count = sum(1 for row in rows if bool(row.get("used_llm")))
    return {
        "total": len(rows),
        "llm": llm_count,
        "fallback": len(rows) - llm_count,
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
