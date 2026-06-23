from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.simulate import (
    MonteCarloDraftTwin,
    SimulationConfig,
    aggregate_shards,
    simulate_shard,
)

SAMPLE_DIR = Path("data/sample")


def _inputs() -> tuple:
    return (
        load_prospects(SAMPLE_DIR),
        load_draft_order(SAMPLE_DIR),
        load_team_needs(SAMPLE_DIR),
        load_mock_signals(SAMPLE_DIR),
    )


def _swarm_report(config: SimulationConfig, shard_count: int):
    prospects, draft_order, team_needs, mock_signals = _inputs()
    draws_per_shard = config.draws // shard_count
    shards = [
        simulate_shard(
            shard_index,
            draws_per_shard,
            prospects,
            draft_order,
            team_needs,
            mock_signals,
            config,
        )
        for shard_index in range(shard_count)
    ]
    return aggregate_shards(shards, prospects, draft_order, config)


def test_single_shard_matches_run_byte_for_byte() -> None:
    prospects, draft_order, team_needs, mock_signals = _inputs()
    config = SimulationConfig(draws=80, seed=123)

    direct = MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
        config=config,
    ).run()
    shard = simulate_shard(
        0,
        config.draws,
        prospects,
        draft_order,
        team_needs,
        mock_signals,
        config,
    )
    swarm = aggregate_shards([shard], prospects, draft_order, config)

    direct_json = json.dumps(asdict(direct), sort_keys=True, ensure_ascii=True)
    swarm_json = json.dumps(asdict(swarm), sort_keys=True, ensure_ascii=True)
    assert swarm_json == direct_json


def test_swarm_is_deterministic_for_fixed_shards_draws_and_seed() -> None:
    config = SimulationConfig(draws=96, seed=987)

    first = _swarm_report(config, shard_count=4)
    second = _swarm_report(config, shard_count=4)

    assert asdict(first) == asdict(second)


def test_multi_shard_report_is_complete_and_probabilities_are_valid() -> None:
    prospects, draft_order, _, _ = _inputs()
    config = SimulationConfig(draws=90, seed=42)

    report = _swarm_report(config, shard_count=3)

    assert report.config.draws == config.draws
    assert len(report.picks) == len(draft_order)
    assert len(report.assigned_picks) == len(draft_order)
    assert len(report.board) == len(prospects)
    assert {milestone.id for milestone in report.milestones} == {
        f"Q{index}" for index in range(1, 8)
    }
    assert all(milestone.status == "answered" for milestone in report.milestones)
    assert all(pick.pick in {team.pick for team in draft_order} for pick in report.picks)
    assert all(0 <= pick.probability <= 1 for pick in report.picks)
    assert all(
        0 <= candidate.probability <= 1
        for pick in report.picks
        for candidate in pick.distribution
    )
    assert all(
        0 <= pick.marginal_probability <= 1 for pick in report.assigned_picks
    )
    assert all(
        0 <= outlook.first_round_probability <= 1 for outlook in report.board
    )
    assert all(
        0 <= team.probability <= 1
        for outlook in report.board
        for team in outlook.team_probabilities
    )
