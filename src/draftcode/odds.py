"""Odds aggregation agent (资金信号 / money signal).

Mirrors the market agent (`draftcode.market`) but turns sportsbook moneyline
odds into a de-vigged implied-probability signal. The fetch layer is external
(WebFetch / crawler / manual); this module only structures supplied odds text
through gpt-5.5 and reduces it to:

- per-prospect ``odds_signal`` (strongest de-vigged implied probability, 0-1)
  and ``odds_rank`` (the pick where that peak occurs = odds-implied landing),
- a per-pick de-vigged probability distribution (``odds_signals.csv``) used as a
  Monte Carlo anchor for the sharp top of the board.

Backward compatible: until ``draftcode odds --apply`` runs, no odds artifacts
exist and the rest of the pipeline is unchanged.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from draftcode import llm_client
from draftcode.divergence import reason_odds_divergence
from draftcode.market import (
    _first_text,
    _format_float,
    _merged_fields,
    _ordered_unique,
    _parse_json_object,
    _prospect_name_index,
    _read_csv_with_fields,
    _resolve_prospect_name,
    _safe_pick,
    _write_csv,
)

ODDS_SIGNAL_COLUMNS = ["abbreviation", "prospect_id", "implied_prob", "source"]


# --------------------------------------------------------------------------- #
# Pure odds math (unit-tested).
# --------------------------------------------------------------------------- #
def american_to_implied(odds: float) -> float:
    """Convert an American moneyline to its (vigged) implied probability."""
    value = float(odds)
    if value < 0:
        return (-value) / ((-value) + 100.0)
    return 100.0 / (value + 100.0)


def devig(probs: list[float]) -> list[float]:
    """Proportional de-vig: ``p_i = q_i / Σq_j``. Zero-sum input -> zeros."""
    total = sum(probs)
    if total <= 0:
        return [0.0 for _ in probs]
    return [p / total for p in probs]


@dataclass(frozen=True)
class OddsQuote:
    source: str
    pick: int
    prospect_name: str
    american_odds: float
    implied_prob: float  # vigged


@dataclass(frozen=True)
class ConsensusOdds:
    prospect_name: str
    odds_rank: int  # pick where the de-vigged implied prob peaks (implied landing)
    odds_signal: float  # peak cross-book de-vigged implied prob (0-1)
    n_sources: int
    sources: list[str]


@dataclass
class OddsReport:
    rankings: list[ConsensusOdds]
    source_names: list[str]
    per_pick_distribution: dict[int, list[tuple[str, float]]]


def aggregate_odds(
    sources: list[tuple[str, str]],
    prospect_names: list[str],
) -> OddsReport:
    """Extract supplied sportsbook odds and aggregate a de-vigged consensus."""
    clean_names = [name for name in dict.fromkeys(n.strip() for n in prospect_names) if name]
    if not clean_names or not sources:
        return OddsReport([], [], {})

    name_index = _prospect_name_index(clean_names)
    # per_pick_probs[pick][name] = list of de-vigged probs, one per source.
    per_pick_probs: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    sources_by_name: dict[str, list[str]] = defaultdict(list)
    source_order: list[str] = []

    for index, (source, text) in enumerate(sources, start=1):
        source_name = source.strip() or f"source-{index}"
        if not text.strip():
            continue
        response = llm_client.complete(
            _build_prompt(source_name, text, clean_names),
            schema=_ODDS_SCHEMA,
            timeout=180,
        )
        payload = _parse_json_object(response) if response is not None else None
        if payload is None:
            continue

        used = False
        for market in _market_items(payload):
            pick = _safe_pick(market.get("pick"))
            entries = market.get("entries")
            if pick is None or not isinstance(entries, list):
                continue
            quotes = _market_quotes(entries, name_index)
            if not quotes:
                continue
            devigged = devig([implied for _, implied in quotes])
            for (name, _), prob in zip(quotes, devigged, strict=True):
                per_pick_probs[pick][name].append(prob)
                sources_by_name[name].append(source_name)
            used = True
        if used:
            source_order.append(source_name)

    if not per_pick_probs:
        return OddsReport([], [], {})

    per_pick_distribution = _consensus_per_pick(per_pick_probs)
    rankings = _consensus_rankings(per_pick_distribution, sources_by_name, source_order)
    return OddsReport(
        rankings=rankings,
        source_names=_ordered_unique(source_order),
        per_pick_distribution=per_pick_distribution,
    )


def apply_odds(
    report: OddsReport,
    data_dir: Path,
    *,
    dry_run: bool = True,
    use_llm_divergence: bool = True,
) -> dict[str, Any]:
    """Write per-prospect odds signals, the per-pick anchor, and axis-2 divergence."""
    prospects_path = data_dir / "prospects.csv"
    draft_order_path = data_dir / "draft_order.csv"
    odds_signals_path = data_dir / "odds_signals.csv"
    axis2_path = data_dir / "divergence_axis2.json"
    axis2_cache_path = data_dir / "divergence_odds_llm.json"

    prospect_fields, prospect_rows = _read_csv_with_fields(prospects_path)
    _, draft_order_rows = _read_csv_with_fields(draft_order_path)

    before_coverage = _odds_coverage(prospect_rows)
    signal_changes = _preview_odds_changes(report, prospect_rows)
    after_coverage = _odds_coverage(prospect_rows)
    odds_signal_rows = _build_odds_signal_rows(report, prospect_rows, draft_order_rows)

    axis2_cache = _load_axis2_cache(axis2_cache_path)
    axis2_records = _build_axis2_records(
        report, prospect_rows, use_llm=use_llm_divergence, cache=axis2_cache
    )

    wrote_csv = False
    if not dry_run and report.rankings:
        _write_csv(
            prospects_path,
            _merged_fields(prospect_fields, ["odds_signal", "odds_rank"]),
            prospect_rows,
        )
        _write_csv(odds_signals_path, ODDS_SIGNAL_COLUMNS, odds_signal_rows)
        axis2_path.write_text(
            json.dumps(axis2_records, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if use_llm_divergence:
            _write_axis2_cache(axis2_cache_path, axis2_cache)
        wrote_csv = True

    result: dict[str, Any] = {
        "dry_run": dry_run,
        "source_names": list(report.source_names),
        "consensus_count": len(report.rankings),
        "odds_coverage_before": before_coverage,
        "odds_coverage_after": after_coverage,
        "odds_signal_changes": signal_changes,
        "odds_signal_rows": len(odds_signal_rows),
        "anchored_picks": sorted(report.per_pick_distribution),
        "axis2_divergence_count": len(axis2_records),
        "axis2_llm_verdicts": sum(
            1 for record in axis2_records.values() if record.get("divergence_odds_llm_verdict")
        ),
        "wrote_csv": wrote_csv,
    }
    audit_path = _write_audit(report, result)
    result["audit_path"] = str(audit_path)
    return result


# --------------------------------------------------------------------------- #
# Aggregation internals.
# --------------------------------------------------------------------------- #
def _market_items(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    for key in ("markets", "pick_markets", "odds"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _market_quotes(
    entries: list[Any],
    name_index: Mapping[str, str | list[str]],
) -> list[tuple[str, float]]:
    quotes: list[tuple[str, float]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        raw_name = _first_text(
            entry,
            [
                "matched_prospect_name",
                "prospect_name",
                "matched_name",
                "name",
                "player_name",
                "player",
            ],
        )
        name = _resolve_prospect_name(raw_name, name_index)
        odds = _safe_number(entry.get("american_odds", entry.get("odds", entry.get("moneyline"))))
        if name is None or odds is None or name in seen:
            continue
        seen.add(name)
        quotes.append((name, american_to_implied(odds)))
    return quotes


def _consensus_per_pick(
    per_pick_probs: dict[int, dict[str, list[float]]],
) -> dict[int, list[tuple[str, float]]]:
    distribution: dict[int, list[tuple[str, float]]] = {}
    for pick, name_probs in per_pick_probs.items():
        means = {name: sum(probs) / len(probs) for name, probs in name_probs.items()}
        total = sum(means.values())
        if total <= 0:
            continue
        ordered = sorted(means.items(), key=lambda item: (-item[1], item[0]))
        distribution[pick] = [(name, prob / total) for name, prob in ordered]
    return dict(sorted(distribution.items()))


def _consensus_rankings(
    per_pick_distribution: dict[int, list[tuple[str, float]]],
    sources_by_name: dict[str, list[str]],
    source_order: list[str],
) -> list[ConsensusOdds]:
    best: dict[str, tuple[int, float]] = {}
    for pick, pairs in per_pick_distribution.items():
        for name, prob in pairs:
            current = best.get(name)
            if current is None or prob > current[1]:
                best[name] = (pick, prob)

    source_index = {source: index for index, source in enumerate(source_order)}
    rankings: list[ConsensusOdds] = []
    for name, (pick, prob) in best.items():
        sources = _ordered_unique(
            sources_by_name.get(name, []),
            key=lambda item: source_index.get(item, len(source_index)),
        )
        rankings.append(
            ConsensusOdds(
                prospect_name=name,
                odds_rank=pick,
                odds_signal=round(prob, 4),
                n_sources=len(sources),
                sources=sources,
            )
        )
    return sorted(
        rankings,
        key=lambda item: (item.odds_rank, -item.odds_signal, item.prospect_name),
    )


# --------------------------------------------------------------------------- #
# Apply internals.
# --------------------------------------------------------------------------- #
def _preview_odds_changes(
    report: OddsReport,
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
                    "odds_signal": consensus.odds_signal,
                    "odds_rank": consensus.odds_rank,
                    "status": "missing_prospect",
                }
            )
            continue
        row = rows_by_name[prospect_name]
        before = row.get("odds_signal", "").strip()
        row["odds_signal"] = _format_float(consensus.odds_signal)
        row["odds_rank"] = str(consensus.odds_rank)
        changes.append(
            {
                "prospect_name": prospect_name,
                "prospect_id": row.get("prospect_id", ""),
                "odds_signal": consensus.odds_signal,
                "odds_rank": consensus.odds_rank,
                "n_sources": consensus.n_sources,
                "sources": consensus.sources,
                "status": "inserted" if not before else "updated",
            }
        )
    return changes


def _build_odds_signal_rows(
    report: OddsReport,
    prospect_rows: list[dict[str, str]],
    draft_order_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    name_index = _prospect_name_index([row.get("name", "") for row in prospect_rows])
    prospect_ids = {
        row.get("name", "").strip(): row.get("prospect_id", "").strip()
        for row in prospect_rows
        if row.get("name", "").strip() and row.get("prospect_id", "").strip()
    }
    abbr_by_pick: dict[int, str] = {}
    for row in draft_order_rows:
        pick = _safe_pick(row.get("pick"))
        abbreviation = row.get("abbreviation", "").strip()
        if pick is not None and abbreviation:
            abbr_by_pick.setdefault(pick, abbreviation)

    rows: list[dict[str, str]] = []
    for pick in sorted(report.per_pick_distribution):
        abbreviation = abbr_by_pick.get(pick)
        if not abbreviation:
            continue
        for name, prob in report.per_pick_distribution[pick]:
            resolved = _resolve_prospect_name(name, name_index)
            prospect_id = prospect_ids.get(resolved) if resolved else None
            if not prospect_id:
                continue
            rows.append(
                {
                    "abbreviation": abbreviation,
                    "prospect_id": prospect_id,
                    "implied_prob": _format_float(round(prob, 4)),
                    "source": "consensus",
                }
            )
    return rows


def _odds_coverage(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if row.get("odds_signal", "").strip())


# --------------------------------------------------------------------------- #
# Axis-2 divergence: expert/mock consensus vs money/odds (two-axis, v3).
# --------------------------------------------------------------------------- #
_AXIS2_GAP_THRESHOLD = 8


def _build_axis2_records(
    report: OddsReport,
    prospect_rows: list[dict[str, str]],
    *,
    use_llm: bool,
    cache: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    name_index = _prospect_name_index([row.get("name", "") for row in prospect_rows])
    info_by_name: dict[str, tuple[str, float | None, str]] = {}
    for row in prospect_rows:
        name = row.get("name", "").strip()
        if not name:
            continue
        market = row.get("market_rank", "").strip()
        info_by_name[name] = (
            row.get("prospect_id", "").strip(),
            float(market) if market else None,
            row.get("primary_position", "").strip(),
        )

    records: dict[str, dict[str, Any]] = {}
    for consensus in report.rankings:
        resolved = _resolve_prospect_name(consensus.prospect_name, name_index)
        if resolved is None or resolved not in info_by_name:
            continue
        prospect_id, market_rank, position = info_by_name[resolved]
        if not prospect_id or market_rank is None:
            continue
        gap = int(round(market_rank - consensus.odds_rank))
        record: dict[str, Any] = {
            "prospect_id": prospect_id,
            "prospect_name": resolved,
            "market_rank": market_rank,
            "odds_rank": consensus.odds_rank,
            "divergence_gap_axis2": gap,
            "divergence_type_axis2": _axis2_type(gap),
            "divergence_reason_axis2": _axis2_reason(
                resolved, market_rank, consensus.odds_rank, gap
            ),
        }
        if use_llm and abs(gap) >= _AXIS2_GAP_THRESHOLD:
            verdict = cache.get(prospect_id)
            if verdict is None:
                verdict = reason_odds_divergence(
                    name=resolved,
                    position=position,
                    market_rank=market_rank,
                    odds_rank=float(consensus.odds_rank),
                    divergence=gap,
                    notes=record["divergence_reason_axis2"],
                )
                if verdict is not None:
                    cache[prospect_id] = verdict
            if verdict is not None:
                record["divergence_odds_llm_verdict"] = verdict["verdict"]
                record["divergence_odds_llm_confidence"] = verdict["confidence"]
                record["divergence_odds_llm_reasoning"] = verdict["reasoning"]
        records[prospect_id] = record
    return records


def _axis2_type(gap: int) -> str:
    if abs(gap) <= _AXIS2_GAP_THRESHOLD:
        return "aligned"
    # gap = market_rank - odds_rank > 0 -> mocks rank later than money -> money bullish.
    return "odds_sharp" if gap > 0 else "mock_sharp"


def _axis2_reason(name: str, market_rank: float, odds_rank: float, gap: int) -> str:
    gap_text = f"+{gap}" if gap > 0 else str(gap)
    if gap > _AXIS2_GAP_THRESHOLD:
        return (
            f"{name}:mock 共识第{market_rank:g}但赔率隐含第{odds_rank:g}(gap{gap_text}):"
            "资金比专家更看好,可能内幕领先。"
        )
    if gap < -_AXIS2_GAP_THRESHOLD:
        return (
            f"{name}:mock 共识第{market_rank:g}高于赔率隐含第{odds_rank:g}(gap{gap_text}):"
            "专家比资金更看好,需防 mock 群体思维。"
        )
    return (
        f"{name}:mock 第{market_rank:g}与赔率第{odds_rank:g}(gap{gap_text}):专家与资金基本一致。"
    )


def _load_axis2_cache(path: Path) -> dict[str, dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    cache: dict[str, dict[str, Any]] = {}
    for prospect_id, entry in payload.items():
        if isinstance(prospect_id, str) and isinstance(entry, dict) and entry.get("verdict"):
            cache[prospect_id] = entry
    return cache


def _write_axis2_cache(path: Path, cache: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_audit(report: OddsReport, result: Mapping[str, Any]) -> Path:
    audit_dir = Path("outputs/odds")
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"odds_{_next_audit_sequence(audit_dir):03d}.json"
    payload = {
        "source_names": list(report.source_names),
        "consensus": [asdict(ranking) for ranking in report.rankings],
        "per_pick_distribution": {
            str(pick): [
                {"prospect_name": name, "devig_prob": round(prob, 4)} for name, prob in pairs
            ]
            for pick, pairs in report.per_pick_distribution.items()
        },
        "application": dict(result),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _next_audit_sequence(audit_dir: Path) -> int:
    highest = 0
    for path in audit_dir.glob("odds_*.json"):
        match = re.fullmatch(r"odds_(\d+)\.json", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _safe_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip().replace("+", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


_ODDS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "markets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pick": {"type": "integer"},
                    "entries": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "raw_player_name": {"type": "string"},
                                "matched_prospect_name": {"type": "string"},
                                "american_odds": {"type": "number"},
                            },
                            "required": [
                                "raw_player_name",
                                "matched_prospect_name",
                                "american_odds",
                            ],
                        },
                    },
                },
                "required": ["pick", "entries"],
            },
        },
    },
    "required": ["markets"],
}


def _build_prompt(source: str, text: str, prospect_names: list[str]) -> str:
    return (
        "You are DraftCode's NBA draft betting-odds extraction agent. "
        "The fetch layer is external; only structure this supplied odds text. "
        "For each draft pick market, extract every player and their American "
        "moneyline odds (negative for favorites, e.g. -550; positive for "
        "underdogs, e.g. 475 for +475). Match every player to exactly one name "
        "from the Chinese prospect pool using cross-language matching, for "
        "example AJ Dybantsa -> AJ 迪班萨. Only include players that clearly "
        "match the pool; never invent odds.\n\n"
        f"Source: {source}\n"
        f"Chinese prospect pool JSON: {json.dumps(prospect_names, ensure_ascii=False)}\n\n"
        "Odds text:\n"
        f"{text.strip()}\n\n"
        "Return markets[]: each item has pick (integer) and entries[]; each entry "
        "has raw_player_name, matched_prospect_name (one exact pool string), and "
        "american_odds (number)."
    )
