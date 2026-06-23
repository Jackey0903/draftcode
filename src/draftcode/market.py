from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from draftcode import llm_client


@dataclass(frozen=True)
class SourceRanking:
    source: str
    prospect_name: str
    projected_pick: int


@dataclass(frozen=True)
class ConsensusMarket:
    prospect_name: str
    consensus_pick: float
    n_sources: int
    sources: list[str]


@dataclass
class MarketReport:
    rankings: list[ConsensusMarket]
    source_names: list[str]


MOCK_SIGNAL_COLUMNS = ["abbreviation", "prospect_id", "signal_strength", "source"]


def aggregate_mocks(
    mocks: list[tuple[str, str]],
    prospect_names: list[str],
) -> MarketReport:
    """Extract externally supplied mock drafts and aggregate source consensus."""
    clean_names = [name for name in dict.fromkeys(name.strip() for name in prospect_names) if name]
    if not clean_names or not mocks:
        return _report_with_source_rankings([], [])

    name_index = _prospect_name_index(clean_names)
    source_rankings: list[SourceRanking] = []
    source_order: list[str] = []
    for index, (source, text) in enumerate(mocks, start=1):
        source_name = source.strip() or f"source-{index}"
        if not text.strip():
            continue

        response = llm_client.complete(
            _build_prompt(source_name, text, clean_names),
            schema=_MARKET_SCHEMA,
            timeout=180,
        )
        payload = _parse_json_object(response) if response is not None else None
        if payload is None:
            continue

        rankings = _parse_source_rankings(payload, source_name, name_index)
        if not rankings:
            continue
        source_order.append(source_name)
        source_rankings.extend(rankings)

    source_rankings = _dedupe_source_rankings(source_rankings)
    if not source_rankings:
        return _report_with_source_rankings([], [])

    return _report_with_source_rankings(
        _consensus_rankings(source_rankings, source_order),
        source_rankings,
    )


def apply_market(report: MarketReport, data_dir: Path, *, dry_run: bool = True) -> dict[str, Any]:
    """Apply consensus market ranks and mock-signal rows, with an audit trace."""
    prospects_path = data_dir / "prospects.csv"
    draft_order_path = data_dir / "draft_order.csv"
    mock_signals_path = data_dir / "mock_signals.csv"

    prospect_fields, prospect_rows = _read_csv_with_fields(prospects_path)
    _, draft_order_rows = _read_csv_with_fields(draft_order_path)

    before_coverage = _market_rank_coverage(prospect_rows)
    rank_changes = _preview_market_rank_changes(report, prospect_rows)
    after_coverage = _market_rank_coverage(prospect_rows)
    mock_signal_rows = _build_mock_signal_rows(report, prospect_rows, draft_order_rows)

    wrote_csv = False
    if not dry_run and report.rankings:
        _write_csv(
            prospects_path,
            _merged_fields(prospect_fields, ["market_rank"]),
            prospect_rows,
        )
        _write_csv(mock_signals_path, MOCK_SIGNAL_COLUMNS, mock_signal_rows)
        wrote_csv = True

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "source_names": list(report.source_names),
        "consensus_count": len(report.rankings),
        "source_ranking_count": len(_source_rankings_from_report(report)),
        "market_rank_coverage_before": before_coverage,
        "market_rank_coverage_after": after_coverage,
        "market_rank_changes": rank_changes,
        "mock_signal_rows": len(mock_signal_rows),
        "mock_signal_sources": _ordered_unique(row["source"] for row in mock_signal_rows),
        "wrote_csv": wrote_csv,
    }
    audit_path = _write_audit(report, result)
    result["audit_path"] = str(audit_path)
    return result


def _build_prompt(source: str, text: str, prospect_names: list[str]) -> str:
    return (
        "You are DraftCode's NBA mock-draft market extraction agent. "
        "The fetch layer is external; only structure this supplied text. "
        "Extract player projected draft pick numbers from the mock draft. "
        "Match every player to exactly one name from the Chinese prospect pool. "
        "Use cross-language matching when the text uses English names, for example "
        "AJ Dybantsa -> AJ 迪班萨. Return only players that clearly match the pool, "
        "and do not invent picks.\n\n"
        f"Source: {source}\n"
        f"Chinese prospect pool JSON: {json.dumps(prospect_names, ensure_ascii=False)}\n\n"
        "Mock draft text:\n"
        f"{text.strip()}\n\n"
        "Use key rankings. Each item must include raw_player_name, "
        "matched_prospect_name, and projected_pick. matched_prospect_name must be "
        "one exact string from the Chinese prospect pool."
    )


def _parse_source_rankings(
    payload: Mapping[str, Any],
    source: str,
    name_index: Mapping[str, str | list[str]],
) -> list[SourceRanking]:
    raw_rankings = _ranking_items(payload)
    rankings: list[SourceRanking] = []
    for raw in raw_rankings:
        if not isinstance(raw, Mapping):
            continue
        raw_name = _first_text(
            raw,
            [
                "matched_prospect_name",
                "prospect_name",
                "chinese_name",
                "matched_name",
                "name",
                "player_name",
                "player",
            ],
        )
        prospect_name = _resolve_prospect_name(raw_name, name_index)
        pick = _safe_pick(
            raw.get(
                "projected_pick",
                raw.get("pick", raw.get("draft_pick", raw.get("rank", raw.get("slot")))),
            )
        )
        if prospect_name is None or pick is None:
            continue
        rankings.append(
            SourceRanking(
                source=source,
                prospect_name=prospect_name,
                projected_pick=pick,
            )
        )
    return rankings


def _ranking_items(payload: Mapping[str, Any]) -> list[Any]:
    for key in ("rankings", "mock_picks", "picks", "players"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _dedupe_source_rankings(rankings: list[SourceRanking]) -> list[SourceRanking]:
    by_key: dict[tuple[str, str], SourceRanking] = {}
    for ranking in rankings:
        key = (ranking.source, ranking.prospect_name)
        current = by_key.get(key)
        if current is None or ranking.projected_pick < current.projected_pick:
            by_key[key] = ranking
    return list(by_key.values())


def _consensus_rankings(
    source_rankings: list[SourceRanking],
    source_order: list[str],
) -> list[ConsensusMarket]:
    picks_by_name: dict[str, list[int]] = defaultdict(list)
    sources_by_name: dict[str, list[str]] = defaultdict(list)
    for ranking in source_rankings:
        picks_by_name[ranking.prospect_name].append(ranking.projected_pick)
        sources_by_name[ranking.prospect_name].append(ranking.source)

    source_order_index = {source: index for index, source in enumerate(source_order)}
    consensus: list[ConsensusMarket] = []
    for prospect_name, picks in picks_by_name.items():
        sources = _ordered_unique(
            sources_by_name[prospect_name],
            key=lambda item: source_order_index.get(item, len(source_order_index)),
        )
        consensus.append(
            ConsensusMarket(
                prospect_name=prospect_name,
                consensus_pick=round(sum(picks) / len(picks), 4),
                n_sources=len(sources),
                sources=sources,
            )
        )
    return sorted(
        consensus,
        key=lambda item: (item.consensus_pick, -item.n_sources, item.prospect_name),
    )


def _preview_market_rank_changes(
    report: MarketReport,
    rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    name_index = _prospect_name_index([row.get("name", "") for row in rows])
    rows_by_name = {row.get("name", "").strip(): row for row in rows if row.get("name", "").strip()}
    changes: list[dict[str, Any]] = []
    for consensus in report.rankings:
        prospect_name = _resolve_prospect_name(consensus.prospect_name, name_index)
        if prospect_name is None or prospect_name not in rows_by_name:
            changes.append(
                {
                    "prospect_name": consensus.prospect_name,
                    "before_market_rank": None,
                    "after_market_rank": consensus.consensus_pick,
                    "n_sources": consensus.n_sources,
                    "sources": consensus.sources,
                    "status": "missing_prospect",
                }
            )
            continue

        row = rows_by_name[prospect_name]
        before = row.get("market_rank", "").strip()
        after = _format_float(consensus.consensus_pick)
        status = "unchanged" if before == after else ("inserted" if not before else "updated")
        row["market_rank"] = after
        changes.append(
            {
                "prospect_name": prospect_name,
                "prospect_id": row.get("prospect_id", ""),
                "before_market_rank": before or None,
                "after_market_rank": consensus.consensus_pick,
                "n_sources": consensus.n_sources,
                "sources": consensus.sources,
                "status": status,
            }
        )
    return changes


def _build_mock_signal_rows(
    report: MarketReport,
    prospect_rows: list[dict[str, str]],
    draft_order_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    name_index = _prospect_name_index([row.get("name", "") for row in prospect_rows])
    prospect_ids = {
        row.get("name", "").strip(): row.get("prospect_id", "").strip()
        for row in prospect_rows
        if row.get("name", "").strip() and row.get("prospect_id", "").strip()
    }
    team_order: dict[str, int] = {}
    for index, row in enumerate(draft_order_rows):
        abbreviation = row.get("abbreviation", "").strip()
        if abbreviation and abbreviation not in team_order:
            team_order[abbreviation] = index

    rows_by_key: dict[tuple[str, str, str], dict[str, str]] = {}
    for consensus in report.rankings:
        prospect_name = _resolve_prospect_name(consensus.prospect_name, name_index)
        if prospect_name is None:
            continue
        prospect_id = prospect_ids.get(prospect_name)
        if not prospect_id:
            continue
        for draft_row in draft_order_rows:
            abbreviation = draft_row.get("abbreviation", "").strip()
            pick = _safe_pick(draft_row.get("pick"))
            if not abbreviation or pick is None:
                continue
            strength = _signal_strength(consensus.consensus_pick, pick)
            if strength <= 0:
                continue
            for source in consensus.sources:
                key = (abbreviation, prospect_id, source)
                current = rows_by_key.get(key)
                formatted = _format_float(strength)
                if current is None or float(current["signal_strength"]) < strength:
                    rows_by_key[key] = {
                        "abbreviation": abbreviation,
                        "prospect_id": prospect_id,
                        "signal_strength": formatted,
                        "source": source,
                    }

    source_order = {source: index for index, source in enumerate(report.source_names)}
    return sorted(
        rows_by_key.values(),
        key=lambda row: (
            team_order.get(row["abbreviation"], 999),
            row["prospect_id"],
            source_order.get(row["source"], 999),
            row["source"],
        ),
    )


def _signal_strength(consensus_pick: float, team_pick: int) -> float:
    distance = abs(team_pick - consensus_pick)
    if distance > 4:
        return 0.0
    return max(0.0, min(1.0, round(0.88 - 0.11 * distance, 4)))


def _prospect_name_index(prospect_names: list[str]) -> dict[str, str | list[str]]:
    index: dict[str, str | list[str]] = {}
    for name in prospect_names:
        clean = name.strip()
        if not clean:
            continue
        index[clean] = clean
        normalized = _normalize_name(clean)
        current = index.get(normalized)
        if current is None:
            index[normalized] = clean
        elif isinstance(current, str) and current != clean:
            index[normalized] = [current, clean]
        elif isinstance(current, list) and clean not in current:
            current.append(clean)
    return index


def _resolve_prospect_name(
    value: str | None,
    name_index: Mapping[str, str | list[str]],
) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None

    direct = name_index.get(clean)
    if isinstance(direct, str):
        return direct

    normalized = _normalize_name(clean)
    exact = name_index.get(normalized)
    if isinstance(exact, str):
        return exact

    matches: list[str] = []
    for key, prospect_name in name_index.items():
        if not isinstance(prospect_name, str) or key == prospect_name:
            continue
        if len(key) >= 3 and (key in normalized or normalized in key):
            matches.append(prospect_name)
    matches = _ordered_unique(matches)
    return matches[0] if len(matches) == 1 else None


def _normalize_name(value: str) -> str:
    normalized = value.casefold()
    normalized = re.sub(r"[\s·・.'’`\"“”\-_,，。()（）/]+", "", normalized)
    return normalized


def _first_text(raw: Mapping[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


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


def _safe_pick(value: object) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        pick = int(value)
        return pick if pick > 0 else None
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"\d+", text)
    if not match:
        return None
    pick = int(match.group(0))
    return pick if pick > 0 else None


def _read_csv_with_fields(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"Required data file is missing: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_audit(report: MarketReport, result: Mapping[str, Any]) -> Path:
    audit_dir = Path("outputs/market")
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"market_{_next_audit_sequence(audit_dir):03d}.json"
    payload = {
        "source_rankings": [asdict(ranking) for ranking in _source_rankings_from_report(report)],
        "source_names": list(report.source_names),
        "consensus": [asdict(ranking) for ranking in report.rankings],
        "application": dict(result),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _next_audit_sequence(audit_dir: Path) -> int:
    highest = 0
    for path in audit_dir.glob("market_*.json"):
        match = re.fullmatch(r"market_(\d+)\.json", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _source_rankings_from_report(report: MarketReport) -> list[SourceRanking]:
    rankings = getattr(report, "source_rankings", [])
    return list(rankings) if isinstance(rankings, list) else []


def _report_with_source_rankings(
    consensus: list[ConsensusMarket],
    source_rankings: list[SourceRanking],
) -> MarketReport:
    report = MarketReport(
        rankings=consensus,
        source_names=_ordered_unique(ranking.source for ranking in source_rankings),
    )
    report.source_rankings = source_rankings
    return report


def _market_rank_coverage(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if row.get("market_rank", "").strip())


def _merged_fields(existing: list[str], required: list[str]) -> list[str]:
    merged = list(existing)
    for field in required:
        if field not in merged:
            merged.append(field)
    return merged or list(required)


def _format_float(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _ordered_unique(values: Any, *, key: Any = None) -> list[Any]:
    unique = list(dict.fromkeys(values))
    if key is not None:
        unique.sort(key=key)
    return unique


_MARKET_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rankings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "raw_player_name": {"type": "string"},
                    "matched_prospect_name": {"type": "string"},
                    "projected_pick": {"type": "integer"},
                },
                "required": ["raw_player_name", "matched_prospect_name", "projected_pick"],
            },
        },
    },
    "required": ["rankings"],
}
