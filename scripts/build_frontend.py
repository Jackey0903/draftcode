#!/usr/bin/env python
"""Regenerate the inline data arrays in web/draft_room.html from pipeline outputs.

Reads ``outputs/twin.json`` + ``outputs/audit.json`` + ``data/processed/draft_order.csv``
and rewrites the ``PICKS`` / ``MS`` / ``AUDIT`` / ``RT`` JavaScript literals in place,
leaving the hand-tuned milestone descriptions, team colours, and render logic alone.

Usage:  python scripts/build_frontend.py  [--html web/draft_room.html]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TWIN = ROOT / "outputs" / "twin.json"
AUDIT = ROOT / "outputs" / "audit.json"
DRAFT_ORDER = ROOT / "data" / "processed" / "draft_order.csv"

# Hand-tuned milestone copy; answers are filled from the live simulation.
MS_META = {
    "Q1": ("第 4–14 顺位中，臂展减赤脚身高 ≥5 吋的超长臂展球员", "人"),
    "Q2": ("训练营助跑弹跳前 3 中，首轮被选中", "人"),
    "Q3": ("首轮 30 人中主打中锋的总数", "个"),
    "Q4": ("第 4–30 顺位首个中锋落点", "顺位"),
    "Q5": ("首轮国际球员总数", "人"),
    "Q6": ("贡献首轮球员最多的机构", ""),
    "Q7": ("训练营手掌长度前 5 中，首轮被选中", "人"),
}
AUDIT_META = [
    ("picks_audited", "顺位全程审计", ""),
    ("odds_backed_picks", "资金信号覆盖", "g"),
    ("axis2_divergence_picks", "专家×资金背离", "r"),
    ("picks_with_explanation", "gpt-5.5 解释", "t"),
    ("gm_influenced_picks", "GM 偏好影响", "b"),
    ("red_team_challenges", "红队质询", "r"),
]


def js_str(value: object) -> str:
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _trade_picks() -> set[int]:
    trades: set[int] = set()
    if DRAFT_ORDER.exists():
        for row in csv.DictReader(DRAFT_ORDER.open(encoding="utf-8")):
            if str(row.get("via_trade")).lower() in {"true", "1"}:
                trades.add(int(row["pick"]))
    return trades


def build_picks(twin: dict) -> str:
    trades = _trade_picks()
    items = []
    for ap in sorted(twin["assigned_picks"], key=lambda r: int(r["pick"])):
        pick = int(ap["pick"])
        prob = round(float(ap["marginal_probability"]), 2)
        flag = 1 if pick in trades else 0
        items.append(
            f"[{pick},{js_str(ap['abbreviation'])},"
            f"{js_str(ap['prospect_name'])},{prob},{flag}]"
        )
    return "const PICKS=[" + ",\n".join(items) + "];"


def build_ms(twin: dict) -> str:
    by_id = {m["id"]: m for m in twin["milestones"]}
    items = []
    for qid, (desc, unit) in MS_META.items():
        meta = by_id.get(qid, {})
        # Prefer the board-consistent answer so the page's milestones match its board.
        answer = meta.get("board_answer_display") or meta.get("answer_display", "")
        if qid == "Q6":
            answer_repr = js_str(answer)
        else:
            try:
                answer_repr = str(int(float(answer)))
            except (TypeError, ValueError):
                answer_repr = js_str(answer)
        items.append(f"[{js_str(qid)},{js_str(desc)},{answer_repr},{js_str(unit)}]")
    return "const MS=[" + ",\n".join(items) + "];"


def build_audit(audit: dict) -> str:
    integrity = audit.get("integrity", {})
    items = [
        f"[{js_str(str(integrity.get(key, 0)))},{js_str(label)},{js_str(color)}]"
        for key, label, color in AUDIT_META
    ]
    return "const AUDIT=[" + ",".join(items) + "];"


def build_rt(audit: dict) -> str:
    questions = audit.get("red_team", {}).get("questions", [])
    items = [js_str(q) for q in questions]
    return "const RT=[" + ",\n".join(items) + "];"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", default=str(ROOT / "web" / "draft_room.html"))
    args = parser.parse_args()

    twin = json.loads(TWIN.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8")) if AUDIT.exists() else {}

    replacements = {
        "PICKS": build_picks(twin),
        "MS": build_ms(twin),
        "AUDIT": build_audit(audit),
        "RT": build_rt(audit),
    }

    html_path = Path(args.html)
    html = html_path.read_text(encoding="utf-8")
    for name, block in replacements.items():
        pattern = rf"const {name}=\[[\s\S]*?\];"
        if not re.search(pattern, html):
            raise SystemExit(f"could not find `const {name}=[...]` in {html_path}")
        html = re.sub(pattern, lambda _m, b=block: b, html, count=1)
    html_path.write_text(html, encoding="utf-8")
    print(f"updated {html_path} from twin.json + audit.json")


if __name__ == "__main__":
    main()
