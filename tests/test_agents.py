from __future__ import annotations

import json
from pathlib import Path

from draftcode import agents
from draftcode.dossier import load_team_dossiers
from draftcode.io import load_prospects

DOSSIER_PATH = Path("data/dossiers/team_dossiers.json")
PROCESSED_DIR = Path("data/processed")


def test_gm_agent_falls_back_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(agents.llm_client, "complete", lambda *args, **kwargs: None)
    dossier = load_team_dossiers(DOSSIER_PATH)["UTA"]
    candidates = load_prospects(PROCESSED_DIR)[:3]

    result = agents.gm_agent(dossier, candidates)

    assert result["abbreviation"] == "UTA"
    assert result["used_llm"] is False
    assert result["adjustments"] == {}
    assert result["ranking"] == []


def test_gm_agent_accepts_fixed_json_response(monkeypatch) -> None:
    candidates = load_prospects(PROCESSED_DIR)[:2]
    target_id = candidates[0].prospect_id

    def fake_complete(*args, **kwargs) -> str:
        return json.dumps(
            {
                "adjustments": {target_id: 0.12, "unknown": 0.04},
                "ranking": [
                    {"prospect_id": target_id, "delta": 0.12, "reason": "upside fit"}
                ],
                "rationale": "high-upside rebuild swing",
            }
        )

    monkeypatch.setattr(agents.llm_client, "complete", fake_complete)
    dossier = load_team_dossiers(DOSSIER_PATH)["UTA"]

    result = agents.gm_agent(dossier, candidates)

    assert result["used_llm"] is True
    assert result["adjustments"] == {target_id: 0.08}
    assert result["ranking"][0]["prospect_id"] == target_id
    assert result["ranking"][0]["delta"] == 0.08


def test_explanation_and_redteam_fallback_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(agents.llm_client, "complete", lambda *args, **kwargs: None)
    pick_record = {
        "pick": 7,
        "abbreviation": "UTA",
        "prospect_id": "p001",
        "prospect_name": "AJ 迪班萨",
        "marginal_probability": 0.64,
        "trace": {
            "top_candidates": [
                {
                    "prospect_id": "p001",
                    "prospect": "AJ 迪班萨",
                    "preference": {"talent": 0.9, "need_fit": 0.7, "persona_fit": 0.8},
                }
            ]
        },
    }

    explanation = agents.explanation_agent(pick_record)
    questions = agents.redteam_agent({"low_confidence_picks": [7]}, [])

    assert "UTA" in explanation
    assert "AJ 迪班萨" in explanation
    assert questions
    assert "Pick 7" in questions[0]


def test_explanation_and_redteam_accept_fixed_json(monkeypatch) -> None:
    def fake_complete(prompt, schema=None, timeout=180) -> str:
        if schema == agents.EXPLANATION_SCHEMA:
            return json.dumps({"text": "LLM explanation"})
        return json.dumps({"questions": ["LLM red-team question"]})

    monkeypatch.setattr(agents.llm_client, "complete", fake_complete)

    explanation = agents.explanation_agent({"pick": 1, "abbreviation": "ATL"})
    questions = agents.redteam_agent({}, [])

    assert explanation == "LLM explanation"
    assert questions == ["LLM red-team question"]
