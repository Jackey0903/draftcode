from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from draftcode.io import load_draft_order, load_mock_signals, load_prospects, load_team_needs
from draftcode.model import DraftPredictor
from draftcode.simulate import MonteCarloDraftTwin, SimulationConfig, _max_weight_assignment

SAMPLE_DIR = Path("data/sample")
PROCESSED_DIR = Path("data/processed")


def _run_simulation(config: SimulationConfig) -> tuple[object, set[str]]:
    prospects = load_prospects(SAMPLE_DIR)
    report = MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=load_draft_order(SAMPLE_DIR),
        team_needs=load_team_needs(SAMPLE_DIR),
        mock_signals=load_mock_signals(SAMPLE_DIR),
        config=config,
    ).run()
    return report, {prospect.prospect_id for prospect in prospects}


def test_determinism() -> None:
    config = SimulationConfig(draws=200, seed=123)

    first, _ = _run_simulation(config)
    second, _ = _run_simulation(config)

    assert asdict(first) == asdict(second)


def test_pick_distribution_shape() -> None:
    config = SimulationConfig(draws=200, seed=42)
    report, prospect_ids = _run_simulation(config)

    assert len(report.picks) == len(load_draft_order(SAMPLE_DIR))
    assert len(report.assigned_picks) == len(load_draft_order(SAMPLE_DIR))
    assert len({pick.prospect_id for pick in report.assigned_picks}) == len(
        report.assigned_picks
    )
    for pick in report.picks:
        assert pick.most_likely_id in prospect_ids
        assert pick.distribution
        assert all(0 <= candidate.probability <= 1 for candidate in pick.distribution)
    for pick in report.assigned_picks:
        assert pick.prospect_id in prospect_ids
        assert 0 <= pick.marginal_probability <= 1


def test_probabilities_valid() -> None:
    config = SimulationConfig(draws=200, seed=42)
    report, _ = _run_simulation(config)

    for pick in report.picks:
        assert 0 <= pick.probability <= 1
    for prospect in report.board:
        assert 0 <= prospect.first_round_probability <= 1
        assert all(0 <= team.probability <= 1 for team in prospect.team_probabilities)


def test_degenerate_matches_deterministic() -> None:
    prospects = load_prospects(SAMPLE_DIR)
    draft_order = load_draft_order(SAMPLE_DIR)
    team_needs = load_team_needs(SAMPLE_DIR)
    mock_signals = load_mock_signals(SAMPLE_DIR)
    config = SimulationConfig(
        draws=50,
        seed=7,
        temperature=1e-6,
        weight_jitter=0.0,
        signal_jitter=0.0,
        need_jitter=0.0,
        board_jitter=0.0,
    )

    report = MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
        config=config,
    ).run()
    deterministic_picks, _ = DraftPredictor().predict(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
    )

    assert [pick.most_likely_id for pick in report.picks] == [
        pick.prospect_id for pick in deterministic_picks
    ]
    assert [pick.prospect_id for pick in report.assigned_picks] == [
        pick.prospect_id for pick in deterministic_picks
    ]


def test_assigned_picks_are_unique_for_full_first_round() -> None:
    report = MonteCarloDraftTwin(
        prospects=load_prospects(PROCESSED_DIR),
        draft_order=load_draft_order(PROCESSED_DIR),
        team_needs=load_team_needs(PROCESSED_DIR),
        mock_signals=load_mock_signals(PROCESSED_DIR),
        config=SimulationConfig(draws=80, seed=42),
    ).run()

    assigned_ids = [pick.prospect_id for pick in report.assigned_picks]

    assert len(assigned_ids) == 30
    assert len(set(assigned_ids)) == 30


def test_assigned_picks_are_deterministic_for_same_seed() -> None:
    config = SimulationConfig(draws=80, seed=42)
    first = MonteCarloDraftTwin(
        prospects=load_prospects(PROCESSED_DIR),
        draft_order=load_draft_order(PROCESSED_DIR),
        team_needs=load_team_needs(PROCESSED_DIR),
        mock_signals=load_mock_signals(PROCESSED_DIR),
        config=config,
    ).run()
    second = MonteCarloDraftTwin(
        prospects=load_prospects(PROCESSED_DIR),
        draft_order=load_draft_order(PROCESSED_DIR),
        team_needs=load_team_needs(PROCESSED_DIR),
        mock_signals=load_mock_signals(PROCESSED_DIR),
        config=config,
    ).run()

    assert [pick.prospect_id for pick in first.assigned_picks] == [
        pick.prospect_id for pick in second.assigned_picks
    ]


def test_hungarian_assignment_finds_max_weight() -> None:
    weights = [
        [10, 9, 0, 0],
        [10, 0, 0, 0],
        [0, 9, 8, 0],
    ]

    assignment = _max_weight_assignment(weights)
    assignment_weight = sum(weights[row][column] for row, column in enumerate(assignment))
    greedy_assignment = [0, 1, 2]
    greedy_weight = sum(
        weights[row][column] for row, column in enumerate(greedy_assignment)
    )

    assert assignment == [1, 0, 2]
    assert assignment_weight == 27
    assert assignment_weight > greedy_weight


def test_milestones_present() -> None:
    config = SimulationConfig(draws=200, seed=42)
    report, _ = _run_simulation(config)
    first_round_length = len(load_draft_order(SAMPLE_DIR))
    answered = {milestone.id: milestone for milestone in report.milestones}

    assert set(answered) == {f"Q{index}" for index in range(1, 8)}
    assert all(milestone.status == "answered" for milestone in answered.values())
    assert answered["Q1"].answer_kind == "count"
    assert answered["Q4"].answer_kind == "pick"
    assert answered["Q6"].answer_kind == "category"

    # Board-consistent answers (used by the answer card + frontend) are populated
    # for every milestone so the submitted card never contradicts the board.
    for milestone in answered.values():
        assert isinstance(milestone.board_answer_display, str)

    for question_id in ["Q1", "Q2", "Q3", "Q5", "Q7"]:
        milestone = answered[question_id]
        assert milestone.expected is not None
        assert 0 <= milestone.expected <= first_round_length
        assert milestone.answer_display.isdigit()

    assert answered["Q4"].expected is not None
    assert answered["Q4"].answer_display.isdigit()
    assert answered["Q6"].expected is None
    assert answered["Q6"].answer_display == ""

    assert answered["Q1"].expected == 0
    assert answered["Q2"].expected == 0
    assert answered["Q3"].expected == 0
    assert answered["Q4"].expected == 0
    assert answered["Q5"].expected == 0
    assert answered["Q7"].expected == 0


def test_odds_anchor_blends_toward_market() -> None:
    candidates = [{"prospect_id": "a"}, {"prospect_id": "b"}]
    blended = MonteCarloDraftTwin._blend_odds_probs(
        candidates, [0.5, 0.5], {"a": 0.9, "b": 0.1}, 0.85
    )
    assert abs(sum(blended) - 1.0) < 1e-9
    assert blended[0] > 0.8  # pulled toward the de-vigged odds favorite

    # No odds market for the slot leaves the softmax distribution untouched.
    assert MonteCarloDraftTwin._blend_odds_probs([{"prospect_id": "a"}], [1.0], None, 0.85) == [1.0]
    assert MonteCarloDraftTwin._blend_odds_probs(candidates, [0.5, 0.5], {}, 0.85) == [0.5, 0.5]

    # Anchor strength is strong at the top and decays to zero down the board.
    assert MonteCarloDraftTwin._odds_lambda(1) > MonteCarloDraftTwin._odds_lambda(4) > 0
    assert MonteCarloDraftTwin._odds_lambda(9) == 0.0
