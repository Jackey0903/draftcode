from __future__ import annotations

import json
from pathlib import Path

from draftcode.audit import build_audit, write_audit


def test_build_audit_joins_prediction_evidence_and_redteam(tmp_path: Path) -> None:
    twin_path, llm_dir, data_dir = _write_synthetic_artifacts(tmp_path)

    audit = build_audit(twin_path=twin_path, llm_dir=llm_dir, data_dir=data_dir)

    assert audit["schema_version"] == 1
    assert audit["red_team"] == {
        "used_llm": True,
        "questions": [
            "Why is Beta not too risky?",
            "What if the market leader is unavailable?",
        ],
    }
    assert audit["integrity"] == {
        "picks_audited": 3,
        "picks_with_explanation": 2,
        "picks_diverging_from_most_likely": 1,
        "llm_divergence_verdicts": 1,
        "gm_influenced_picks": 1,
        "odds_backed_picks": 0,
        "axis2_divergence_picks": 0,
        "red_team_challenges": 2,
        "low_confidence_picks": 1,
    }

    pick_one, pick_two, pick_three = audit["picks"]
    assert pick_one["pick"] == 1
    assert pick_one["prospect_id"] == "p1"
    assert pick_one["prospect_name"] == "Alpha"
    assert pick_one["assigned_probability"] == 0.26
    assert pick_one["most_likely_probability"] == 0.27
    assert pick_one["matches_most_likely"] is True
    assert pick_one["explanation"] == "Alpha fits the first pick."
    assert pick_one["divergence"] is None
    assert pick_one["gm_influence"] is None

    assert pick_two["pick"] == 2
    assert pick_two["prospect_id"] == "p2"
    assert pick_two["most_likely_id"] == "p3"
    assert pick_two["matches_most_likely"] is False
    assert pick_two["low_confidence"] is True
    assert pick_two["explanation"] == "Beta is the assigned upside swing."
    assert pick_two["divergence"] == {
        "verdict": "talent_undervalued",
        "market_weight": 0.65,
        "confidence": 0.64,
        "reasoning": "Market is more reliable here.",
    }
    assert pick_two["gm_influence"] == {
        "delta": 0.04,
        "rationale": "Needs a creator next to the current core.",
    }

    assert pick_three["pick"] == 3
    assert pick_three["prospect_id"] == "p3"
    assert pick_three["matches_most_likely"] is True
    assert pick_three["explanation"] is None
    assert pick_three["divergence"] is None
    assert pick_three["gm_influence"] is None


def test_build_audit_gracefully_degrades_without_optional_artifacts(
    tmp_path: Path,
) -> None:
    twin_path, llm_dir, data_dir = _write_synthetic_artifacts(tmp_path)
    for path in [
        llm_dir / "explanations.json",
        llm_dir / "redteam.json",
        llm_dir / "gm_preferences.json",
        data_dir / "prospects.csv",
    ]:
        path.unlink()

    audit = build_audit(twin_path=twin_path, llm_dir=llm_dir, data_dir=data_dir)

    assert len(audit["picks"]) == 3
    assert audit["sources"] == {
        "twin": str(twin_path),
        "explanations": None,
        "redteam": None,
        "gm_preferences": None,
        "prospects": None,
        "odds": None,
        "axis2": None,
    }
    assert audit["red_team"] == {"used_llm": False, "questions": []}
    assert all(pick["explanation"] is None for pick in audit["picks"])
    assert all(pick["divergence"] is None for pick in audit["picks"])
    assert all(pick["gm_influence"] is None for pick in audit["picks"])
    assert audit["integrity"]["picks_audited"] == 3
    assert audit["integrity"]["picks_with_explanation"] == 0
    assert audit["integrity"]["red_team_challenges"] == 0


def test_write_audit_round_trips_json_and_renders_markdown(tmp_path: Path) -> None:
    twin_path, llm_dir, data_dir = _write_synthetic_artifacts(tmp_path)
    audit = build_audit(twin_path=twin_path, llm_dir=llm_dir, data_dir=data_dir)
    out_json = tmp_path / "outputs" / "audit.json"
    out_md = tmp_path / "outputs" / "audit.md"

    write_audit(audit, out_json=out_json, out_md=out_md)

    assert json.loads(out_json.read_text(encoding="utf-8")) == audit
    markdown = out_md.read_text(encoding="utf-8")
    assert markdown
    assert "Why is Beta not too risky?" in markdown
    assert "| 2 | CHA | Beta | 0.31" in markdown


def _write_synthetic_artifacts(tmp_path: Path) -> tuple[Path, Path, Path]:
    twin_path = tmp_path / "outputs" / "twin.json"
    llm_dir = tmp_path / "outputs" / "llm"
    data_dir = tmp_path / "data" / "processed"
    twin_path.parent.mkdir(parents=True)
    llm_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    _write_json(
        twin_path,
        {
            "config": {"draws": 3, "seed": 7},
            "picks": [
                {
                    "pick": 1,
                    "team": "Washington Wizards",
                    "abbreviation": "WAS",
                    "most_likely_id": "p1",
                    "most_likely_name": "Alpha",
                    "probability": 0.27,
                    "distribution": [],
                    "low_confidence": False,
                },
                {
                    "pick": 2,
                    "team": "Charlotte Hornets",
                    "abbreviation": "CHA",
                    "most_likely_id": "p3",
                    "most_likely_name": "Gamma",
                    "probability": 0.40,
                    "distribution": [],
                    "low_confidence": True,
                },
                {
                    "pick": 3,
                    "team": "Utah Jazz",
                    "abbreviation": "UTA",
                    "most_likely_id": "p3",
                    "most_likely_name": "Gamma",
                    "probability": 0.50,
                    "distribution": [],
                    "low_confidence": False,
                },
            ],
            "assigned_picks": [
                {
                    "pick": 1,
                    "team": "Washington Wizards",
                    "abbreviation": "WAS",
                    "prospect_id": "p1",
                    "prospect_name": "Alpha",
                    "marginal_probability": 0.26,
                },
                {
                    "pick": 2,
                    "team": "Charlotte Hornets",
                    "abbreviation": "CHA",
                    "prospect_id": "p2",
                    "prospect_name": "Beta",
                    "marginal_probability": 0.31,
                },
                {
                    "pick": 3,
                    "team": "Utah Jazz",
                    "abbreviation": "UTA",
                    "prospect_id": "p3",
                    "prospect_name": "Gamma",
                    "marginal_probability": 0.20,
                },
            ],
            "board": [
                {
                    "prospect_id": "p1",
                    "name": "Alpha",
                    "first_round_probability": 1.0,
                    "team_probabilities": [],
                }
            ],
            "milestones": [
                {
                    "id": "Q1",
                    "status": "answered",
                    "answer_display": "1",
                }
            ],
            "low_confidence_picks": [2],
        },
    )
    _write_json(
        llm_dir / "explanations.json",
        {
            "schema_version": 1,
            "mode": "llm-once",
            "picks": [
                {
                    "abbreviation": "WAS",
                    "pick": 1,
                    "prospect_id": "p1",
                    "prospect_name": "Alpha",
                    "team": "Washington Wizards",
                    "text": "Alpha fits the first pick.",
                    "used_llm": True,
                },
                {
                    "abbreviation": "CHA",
                    "pick": 2,
                    "prospect_id": "p2",
                    "prospect_name": "Beta",
                    "team": "Charlotte Hornets",
                    "text": "Beta is the assigned upside swing.",
                    "used_llm": True,
                },
            ],
        },
    )
    _write_json(
        llm_dir / "redteam.json",
        {
            "schema_version": 1,
            "mode": "llm-once",
            "used_llm": True,
            "questions": [
                "Why is Beta not too risky?",
                "What if the market leader is unavailable?",
            ],
        },
    )
    _write_json(
        llm_dir / "gm_preferences.json",
        {
            "schema_version": 1,
            "mode": "llm-once",
            "teams": {
                "CHA": {
                    "abbreviation": "CHA",
                    "adjustments": {"p2": 0.04, "p1": 0.0},
                    "ranking": ["p2"],
                    "rationale": "Needs a creator next to the current core.",
                    "team": "Charlotte Hornets",
                    "used_llm": True,
                }
            },
        },
    )
    (data_dir / "prospects.csv").write_text(
        "\n".join(
            [
                "prospect_id,name,divergence_llm_verdict,"
                "divergence_llm_market_weight,divergence_llm_confidence,"
                "divergence_llm_reasoning",
                "p1,Alpha,,,,",
                "p2,Beta,talent_undervalued,0.65,0.64,Market is more reliable here.",
                "p3,Gamma,,,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return twin_path, llm_dir, data_dir


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
