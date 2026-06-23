"""Unified consensus re-ranking: fuse talent + market(mock) + money(odds) for ALL
players, after the market and odds agents have been applied.

The official normalizer ranks handbook players by a talent+market blend but ranks
non-handbook ("fallback") players by talent only — so a market darling who is not
in the talent handbook (mocked/bet high but no scouting-grade data) gets buried.
This step re-derives ``consensus_rank`` for EVERY prospect from all three signals,
with the market as the anchor (the project thesis). Missing signals count as 0
(no market/odds support => lower rank), so players the market never rates sink and
heavily-mocked/bet players rise — regardless of handbook membership.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

# Market-anchored weights (talent is the adjustment); they sum to 1 and are NOT
# renormalized for missing signals, so "no market support" genuinely lowers a rank.
W_TALENT = 0.35
W_MARKET = 0.45
W_ODDS = 0.20


def fuse_consensus_ranks(data_dir: Path) -> dict[str, Any]:
    """Recompute ``fused_score``/``consensus_rank`` from talent + market + odds."""
    path = Path(data_dir) / "prospects.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if not rows:
        return {"count": 0}

    denom = max(len(rows) - 1, 1)
    for row in rows:
        talent = _num(row.get("talent_signal")) or 0.0
        market = _market_signal(row, denom)
        odds = _num(row.get("odds_signal")) or 0.0
        fused = W_TALENT * talent + W_MARKET * market + W_ODDS * odds
        row["fused_score"] = f"{fused:.6f}"

    ranked = sorted(rows, key=lambda r: (-float(r["fused_score"]), r.get("name", "")))
    for rank, row in enumerate(ranked, start=1):
        row["consensus_rank"] = str(rank)

    rows.sort(key=lambda r: r.get("prospect_id", ""))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})

    top = [(r["consensus_rank"], r.get("name", "")) for r in ranked[:5]]
    return {"count": len(rows), "top5": top}


def _market_signal(row: dict[str, str], denom: int) -> float:
    """Market signal in [0,1]: prefer stored market_signal, else from market_rank."""
    signal = _num(row.get("market_signal"))
    if signal is not None:
        return max(0.0, min(1.0, signal))
    market_rank = _num(row.get("market_rank"))
    if market_rank is not None:
        return max(0.0, min(1.0, 1.0 - (market_rank - 1.0) / denom))
    return 0.0


def _num(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
