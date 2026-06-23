from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from draftcode import divergence
from draftcode.official import PoolProspect, ProspectBuild, _assign_consensus_ranks


def test_reason_divergence_parses_valid_and_code_fenced_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "verdict": "talent_undervalued",
        "adjusted_market_weight": 0.85,
        "confidence": 0.8,
        "reasoning": "Injury context suppresses the talent composite.",
    }

    assert _reason_with_response(monkeypatch, json.dumps(payload)) == payload
    fenced = f"```json\n{json.dumps(payload)}\n```"
    assert _reason_with_response(monkeypatch, fenced) == payload


@pytest.mark.parametrize(
    "response",
    [
        "not json",
        json.dumps(
            {
                "verdict": "talent_undervalued",
                "adjusted_market_weight": 1.2,
                "confidence": 0.8,
                "reasoning": "Too much market weight.",
            }
        ),
        json.dumps(
            {
                "verdict": "talent_undervalued",
                "adjusted_market_weight": 0.85,
                "confidence": 0.8,
                "reasoning": " ",
            }
        ),
    ],
)
def test_reason_divergence_rejects_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch,
    response: str,
) -> None:
    assert _reason_with_response(monkeypatch, response) is None


def test_llm_talent_undervalued_raises_fused_score_and_rank(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baseline = _run_rule_baseline()
    calls: list[dict[str, Any]] = []

    def fake_reason_divergence(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "verdict": "talent_undervalued",
            "adjusted_market_weight": 0.85,
            "confidence": 0.8,
            "reasoning": "Healthy upside makes the public market signal informative.",
        }

    monkeypatch.setattr(divergence, "reason_divergence", fake_reason_divergence)
    builds = _minimal_handbook_builds()

    _assign_consensus_ranks(builds, out_dir=tmp_path, use_llm_divergence=True)

    target = _target_build(builds)
    assert len(calls) == 1
    assert target.row["fused_score"] > baseline["fused_score"]
    assert target.row["consensus_rank"] < baseline["consensus_rank"]
    assert target.row["divergence_llm_verdict"] == "talent_undervalued"
    assert "[gpt-5.5:talent_undervalued w=0.85 conf=0.8" in target.row[
        "divergence_reason"
    ]


def test_llm_market_hype_keeps_fused_score_conservative(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baseline = _run_rule_baseline()

    def fake_reason_divergence(**kwargs: Any) -> dict[str, Any]:
        return {
            "verdict": "market_hype",
            "adjusted_market_weight": 0.25,
            "confidence": 0.8,
            "reasoning": "The market is ahead of the profile.",
        }

    monkeypatch.setattr(divergence, "reason_divergence", fake_reason_divergence)
    builds = _minimal_handbook_builds()

    _assign_consensus_ranks(builds, out_dir=tmp_path, use_llm_divergence=True)

    target = _target_build(builds)
    assert target.row["fused_score"] < baseline["fused_score"]
    assert target.row["divergence_llm_verdict"] == "market_hype"


def test_llm_none_keeps_rule_fusion_exact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    baseline = _run_rule_baseline()
    calls = 0

    def fake_reason_divergence(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(divergence, "reason_divergence", fake_reason_divergence)
    builds = _minimal_handbook_builds()

    _assign_consensus_ranks(builds, out_dir=tmp_path, use_llm_divergence=True)

    target = _target_build(builds)
    assert calls == 1
    assert target.row["fused_score"] == baseline["fused_score"]
    assert target.row["consensus_rank"] == baseline["consensus_rank"]
    assert target.row["divergence_llm_verdict"] == ""
    assert json.loads((tmp_path / "divergence_llm.json").read_text(encoding="utf-8")) == {}


def test_llm_divergence_cache_is_deterministic_and_skips_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "divergence_llm.json"
    cache = {
        "p051": {
            "verdict": "talent_undervalued",
            "adjusted_market_weight": 0.85,
            "confidence": 0.8,
            "reasoning": "Cached injury-context adjudication.",
        }
    }
    cache_path.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    calls = 0

    def fake_reason_divergence(**kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(divergence, "reason_divergence", fake_reason_divergence)

    first_builds = _minimal_handbook_builds()
    _assign_consensus_ranks(first_builds, out_dir=tmp_path, use_llm_divergence=True)
    first_bytes = cache_path.read_bytes()

    second_builds = _minimal_handbook_builds()
    _assign_consensus_ranks(second_builds, out_dir=tmp_path, use_llm_divergence=True)
    second_bytes = cache_path.read_bytes()

    assert calls == 0
    assert first_bytes == second_bytes
    assert _target_build(first_builds).row["divergence_llm_verdict"] == "talent_undervalued"


def _reason_with_response(
    monkeypatch: pytest.MonkeyPatch,
    response: str,
) -> dict[str, Any] | None:
    monkeypatch.setattr(divergence.llm_client, "complete", lambda prompt, schema=None: response)
    return divergence.reason_divergence(
        name="达林 彼得森",
        position="G",
        talent_profile={
            "talent_composite": 44,
            "true_shooting_pct": 0.5897,
            "usage_rate": 24.0,
            "archetype": "guard",
        },
        talent_rank=14,
        market_rank=1.5,
        divergence=-12,
        notes="market_hype baseline",
    )


def _run_rule_baseline() -> dict[str, Any]:
    builds = _minimal_handbook_builds()
    _assign_consensus_ranks(builds, out_dir=None, use_llm_divergence=False)
    return dict(_target_build(builds).row)


def _minimal_handbook_builds() -> list[ProspectBuild]:
    builds = [
        _build(
            pool_index=rank,
            prospect_id=f"p{rank:03d}",
            name=f"Prospect {rank}",
            talent_composite=100 - rank,
            espn_rank=rank + 1,
        )
        for rank in range(1, 12)
    ]
    builds.append(
        _build(
            pool_index=51,
            prospect_id="p051",
            name="达林 彼得森",
            talent_composite=80,
            espn_rank=1,
        )
    )
    return builds


def _build(
    *,
    pool_index: int,
    prospect_id: str,
    name: str,
    talent_composite: float,
    espn_rank: int,
) -> ProspectBuild:
    pool = PoolProspect(
        pool_index=pool_index,
        prospect_id=prospect_id,
        name=name,
        position="PG",
        school="Test",
        raw_country="美国",
    )
    row: dict[str, Any] = {
        "prospect_id": prospect_id,
        "name": name,
        "primary_position": "G",
        "archetype": "guard",
        "consensus_rank": None,
        "age": 19.0,
        "height_in": 76.0,
        "wingspan_in": 81.0,
        "usage_rate": 24.0,
        "true_shooting_pct": 0.5897,
        "assist_rate": 22.0,
        "rebound_rate": 9.0,
        "stock_rate": 2.5,
        "notes": "test",
        "barefoot_height_in": None,
        "hand_length_in": None,
        "hand_width_in": None,
        "standing_reach_in": None,
        "weight_lb": None,
        "max_vertical_in": None,
        "standing_vertical_in": None,
        "school": "Test",
        "country": "美国",
        "is_international": False,
        "is_center": False,
        "talent_composite": talent_composite,
        "espn_rank": espn_rank,
        "model_pick_low": espn_rank,
        "board_source": "handbook",
        "talent_rank": None,
        "market_rank": None,
        "talent_signal": None,
        "market_signal": None,
        "divergence_gap": None,
        "divergence_type": "",
        "divergence_reason": "",
        "divergence_llm_verdict": "",
        "divergence_llm_market_weight": None,
        "divergence_llm_confidence": None,
        "divergence_llm_reasoning": "",
        "fused_score": None,
    }
    return ProspectBuild(
        pool=pool,
        row=row,
        shooting_pct=None,
        raw_height_in=None,
        raw_wingspan_in=None,
        max_vertical_in=None,
        hand_length_in=None,
        unknown_country=False,
    )


def _target_build(builds: list[ProspectBuild]) -> ProspectBuild:
    return next(build for build in builds if build.pool.prospect_id == "p051")
