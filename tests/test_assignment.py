from __future__ import annotations

from collections import Counter, defaultdict

from draftcode.schemas import Prospect, Team
from draftcode.simulate import MonteCarloDraftTwin, ShardResult, SimulationConfig, TwinReport

DRAW_COUNT = 100
PICK_COUNT = 30
DISPERSED_PROSPECT_ID = "p31"


def _prospects() -> list[Prospect]:
    return [
        Prospect(
            prospect_id=f"p{index:02d}",
            name=f"Prospect {index:02d}",
            primary_position="G",
            archetype="test",
            consensus_rank=index,
            age=19.0,
            height_in=78.0,
            wingspan_in=80.0,
            usage_rate=0.2,
            true_shooting_pct=0.55,
            assist_rate=0.1,
            rebound_rate=0.1,
            stock_rate=0.02,
        )
        for index in range(1, PICK_COUNT + 2)
    ]


def _draft_order() -> list[Team]:
    return [
        Team(
            pick=index,
            team=f"Team {index:02d}",
            abbreviation=f"T{index:02d}",
        )
        for index in range(1, PICK_COUNT + 1)
    ]


def _milestone_values() -> dict[str, list[float | str]]:
    values: dict[str, list[float | str]] = {
        f"Q{index}": [0.0] * DRAW_COUNT for index in range(1, 8)
    }
    values["Q6"] = [""] * DRAW_COUNT
    return values


def _dispersed_high_probability_shard() -> ShardResult:
    pick_counts: list[dict[str, int]] = []
    prospect_counts: Counter[str] = Counter()
    prospect_team_counts: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for index in range(1, PICK_COUNT + 1):
        leader_id = f"p{index:02d}"
        team_abbreviation = f"T{index:02d}"
        dispersed_count = 4 if index <= 10 else 3
        counts = {
            leader_id: DRAW_COUNT - dispersed_count,
            DISPERSED_PROSPECT_ID: dispersed_count,
        }
        pick_counts.append(counts)
        for prospect_id, count in counts.items():
            prospect_counts[prospect_id] += count
            prospect_team_counts[prospect_id][team_abbreviation] += count

    return ShardResult(
        shard_index=0,
        draws=DRAW_COUNT,
        pick_counts=pick_counts,
        prospect_counts=dict(sorted(prospect_counts.items())),
        prospect_team_counts={
            prospect_id: dict(sorted(team_counts.items()))
            for prospect_id, team_counts in sorted(prospect_team_counts.items())
        },
        milestone_values=_milestone_values(),
    )


def _report() -> tuple[list[Prospect], list[Team], ShardResult, TwinReport]:
    prospects = _prospects()
    draft_order = _draft_order()
    config = SimulationConfig(draws=DRAW_COUNT, seed=1)
    shard = _dispersed_high_probability_shard()
    report = MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=[],
        mock_signals=[],
        config=config,
    ).aggregate_shards([shard])
    return prospects, draft_order, shard, report


def _expected_first_round_pool(
    prospects: list[Prospect],
    draft_order: list[Team],
    shard: ShardResult,
) -> set[str]:
    marginal_counts: Counter[str] = Counter()
    for counts in shard.pick_counts:
        marginal_counts.update(counts)

    ranked = sorted(
        prospects,
        key=lambda prospect: (
            -shard.prospect_counts.get(prospect.prospect_id, 0),
            -marginal_counts[prospect.prospect_id],
            prospect.consensus_rank,
            prospect.prospect_id,
        ),
    )
    return {prospect.prospect_id for prospect in ranked[: len(draft_order)]}


def test_dispersed_high_first_round_probability_prospect_stays_assigned() -> None:
    _, _, _, report = _report()

    assigned_ids = [pick.prospect_id for pick in report.assigned_picks]
    most_likely_ids = [pick.most_likely_id for pick in report.picks]
    dispersed_outlook = next(
        outlook
        for outlook in report.board
        if outlook.prospect_id == DISPERSED_PROSPECT_ID
    )

    assert dispersed_outlook.first_round_probability == 1.0
    assert DISPERSED_PROSPECT_ID not in most_likely_ids
    assert DISPERSED_PROSPECT_ID in assigned_ids


def test_assigned_picks_are_unique_and_from_first_round_top_pool() -> None:
    prospects, draft_order, shard, report = _report()

    assigned_ids = [pick.prospect_id for pick in report.assigned_picks]
    expected_pool = _expected_first_round_pool(prospects, draft_order, shard)

    assert len(assigned_ids) == PICK_COUNT
    assert len(set(assigned_ids)) == PICK_COUNT
    assert set(assigned_ids) == expected_pool
