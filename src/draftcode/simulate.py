from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace

from draftcode.dossier import TeamDossier
from draftcode.model import DraftPredictor
from draftcode.preference import preference_score
from draftcode.schemas import MockSignal, ModelWeights, Prospect, Team, TeamNeed


@dataclass(frozen=True)
class SimulationConfig:
    """Configuration for a deterministic Monte Carlo draft twin run."""

    draws: int = 1000
    seed: int = 42
    temperature: float = 0.06
    top_k: int = 5
    weight_jitter: float = 0.15
    signal_jitter: float = 0.25
    need_jitter: float = 0.15
    board_jitter: float = 0.05
    low_confidence_threshold: float = 0.5
    wingspan_threshold: float = 84.0


_MilestoneValue = float | str
_MilestoneCalculator = Callable[[list[str]], _MilestoneValue]
_GM_DELTA_LIMIT = 0.08
_GM_PREFERENCE_WEIGHT = 0.50


@dataclass(frozen=True)
class CandidateProb:
    """Selection probability for a prospect within one pick distribution."""

    prospect_id: str
    name: str
    probability: float


@dataclass(frozen=True)
class PickDistribution:
    """Monte Carlo probability distribution for one draft pick."""

    pick: int
    team: str
    abbreviation: str
    most_likely_id: str
    most_likely_name: str
    probability: float
    distribution: list[CandidateProb]
    low_confidence: bool


@dataclass(frozen=True)
class AssignedPick:
    """Globally unique pick assignment optimized from marginal pick probabilities."""

    pick: int
    team: str
    abbreviation: str
    prospect_id: str
    prospect_name: str
    marginal_probability: float


@dataclass(frozen=True)
class TeamProb:
    """Probability that a prospect is selected by a team."""

    abbreviation: str
    probability: float


@dataclass(frozen=True)
class ProspectOutlook:
    """Prospect-level first-round and team landing probabilities."""

    prospect_id: str
    name: str
    first_round_probability: float
    team_probabilities: list[TeamProb]


@dataclass(frozen=True)
class MilestoneAnswer:
    """Aggregated answer for one milestone question."""

    id: str
    question: str
    status: str
    answer_kind: str
    answer_display: str
    expected: float | None
    p10: float | None
    p90: float | None
    confidence: float | None
    detail: str
    # Answer recomputed on the single assigned board so the submitted card and the
    # public board never contradict each other; answer_display/expected keep the
    # full Monte Carlo distribution view for audit.
    board_answer_display: str = ""


@dataclass(frozen=True)
class ShardResult:
    """Raw Monte Carlo counts from one independently seeded scenario shard."""

    shard_index: int
    draws: int
    pick_counts: list[dict[str, int]]
    prospect_counts: dict[str, int]
    prospect_team_counts: dict[str, dict[str, int]]
    milestone_values: dict[str, list[_MilestoneValue]]


@dataclass(frozen=True)
class TwinReport:
    """Complete Milestone-Aware Draft Twin output."""

    config: SimulationConfig
    picks: list[PickDistribution]
    assigned_picks: list[AssignedPick]
    board: list[ProspectOutlook]
    milestones: list[MilestoneAnswer]
    low_confidence_picks: list[int]


@dataclass(frozen=True)
class _MilestoneDefinition:
    id: str
    question: str
    answer_kind: str
    detail: str
    calculator: _MilestoneCalculator


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _max_weight_assignment(weights: list[list[int]]) -> list[int]:
    """Return one max-weight row-to-column assignment for a rectangular matrix."""
    if not weights:
        return []
    row_count = len(weights)
    column_count = len(weights[0])
    if column_count == 0:
        raise ValueError("Assignment matrix must include at least one column")
    if any(len(row) != column_count for row in weights):
        raise ValueError("Assignment matrix rows must have equal length")
    if row_count > column_count:
        raise ValueError("Assignment matrix must have at least as many columns as rows")

    max_weight = max(max(row) for row in weights)
    tie_base = row_count * column_count + 1
    costs = [
        [(max_weight - weight) * tie_base + column_index for column_index, weight in enumerate(row)]
        for row in weights
    ]
    return _min_cost_assignment(costs)


def _min_cost_assignment(costs: list[list[int]]) -> list[int]:
    """Kuhn-Munkres/Hungarian algorithm for rows <= columns."""
    row_count = len(costs)
    column_count = len(costs[0])
    potential_rows = [0] * (row_count + 1)
    potential_columns = [0] * (column_count + 1)
    matched_row_for_column = [0] * (column_count + 1)
    previous_column = [0] * (column_count + 1)

    for row in range(1, row_count + 1):
        matched_row_for_column[0] = row
        current_column = 0
        min_reduced_cost = [math.inf] * (column_count + 1)
        used = [False] * (column_count + 1)

        while True:
            used[current_column] = True
            current_row = matched_row_for_column[current_column]
            delta = math.inf
            next_column = 0
            for column in range(1, column_count + 1):
                if used[column]:
                    continue
                reduced_cost = (
                    costs[current_row - 1][column - 1]
                    - potential_rows[current_row]
                    - potential_columns[column]
                )
                if reduced_cost < min_reduced_cost[column]:
                    min_reduced_cost[column] = reduced_cost
                    previous_column[column] = current_column
                if min_reduced_cost[column] < delta:
                    delta = min_reduced_cost[column]
                    next_column = column

            for column in range(column_count + 1):
                if used[column]:
                    potential_rows[matched_row_for_column[column]] += delta
                    potential_columns[column] -= delta
                else:
                    min_reduced_cost[column] -= delta

            current_column = next_column
            if matched_row_for_column[current_column] == 0:
                break

        while True:
            next_column = previous_column[current_column]
            matched_row_for_column[current_column] = matched_row_for_column[next_column]
            current_column = next_column
            if current_column == 0:
                break

    assignment = [-1] * row_count
    for column in range(1, column_count + 1):
        row = matched_row_for_column[column]
        if row:
            assignment[row - 1] = column - 1
    return assignment


class MonteCarloDraftTwin:
    """Run reproducible draft simulations and aggregate pick and milestone probabilities."""

    def __init__(
        self,
        prospects: list[Prospect],
        draft_order: list[Team],
        team_needs: list[TeamNeed],
        mock_signals: list[MockSignal],
        config: SimulationConfig,
        weights: ModelWeights | None = None,
        dossiers: dict[str, TeamDossier] | None = None,
        gm_preferences: dict[str, dict[str, float]] | None = None,
    ) -> None:
        self.prospects = prospects
        self.draft_order = sorted(draft_order, key=lambda row: row.pick)
        self.team_needs = team_needs
        self.mock_signals = mock_signals
        self.config = config
        self.weights = weights or ModelWeights()
        self.dossiers = dossiers
        self.gm_preferences = _normalize_gm_preferences(gm_preferences)
        self.preference_trace: list[dict[str, object]] = []
        self._prospect_index = {prospect.prospect_id: prospect for prospect in prospects}
        self._prospect_rank = {
            prospect.prospect_id: prospect.consensus_rank for prospect in prospects
        }
        self._team_order = {
            team.abbreviation: index for index, team in enumerate(self.draft_order)
        }
        self._top_max_vertical_ids = self._top_n_prospect_ids("max_vertical_in", 3)
        self._top_hand_length_ids = self._top_n_prospect_ids("hand_length_in", 5)
        self._milestones = self._build_milestone_definitions()

    def run(self) -> TwinReport:
        """Execute configured scenarios and return an aggregated twin report."""
        return self.aggregate_shards([self.simulate_shard(0, self.config.draws)])

    def simulate_shard(self, shard_index: int, draws: int) -> ShardResult:
        """Execute one deterministic shard and return mergeable raw counts."""
        self._validate_inputs(draws)
        rng = random.Random(self.config.seed + shard_index * 1_000_003)
        pick_counters: list[Counter[str]] = [Counter() for _ in self.draft_order]
        prospect_counter: Counter[str] = Counter()
        prospect_team_counters: dict[str, Counter[str]] = defaultdict(Counter)
        milestone_values: dict[str, list[_MilestoneValue]] = {
            milestone.id: [] for milestone in self._milestones
        }

        capture_trace = (bool(self.dossiers) or bool(self.gm_preferences)) and shard_index == 0
        if capture_trace:
            self.preference_trace = []

        for draw_index in range(draws):
            selected_ids = self._simulate_one(
                rng,
                capture_trace=capture_trace and draw_index == 0,
            )
            for index, prospect_id in enumerate(selected_ids):
                team = self.draft_order[index]
                pick_counters[index][prospect_id] += 1
                prospect_counter[prospect_id] += 1
                prospect_team_counters[prospect_id][team.abbreviation] += 1
            for milestone in self._milestones:
                milestone_values[milestone.id].append(milestone.calculator(selected_ids))

        return ShardResult(
            shard_index=shard_index,
            draws=draws,
            pick_counts=[_sorted_count_dict(counter) for counter in pick_counters],
            prospect_counts=_sorted_count_dict(prospect_counter),
            prospect_team_counts={
                prospect_id: _sorted_count_dict(counter)
                for prospect_id, counter in sorted(prospect_team_counters.items())
            },
            milestone_values=milestone_values,
        )

    def aggregate_shards(self, shard_results: list[ShardResult]) -> TwinReport:
        """Merge shard raw counts and build the same report shape as ``run``."""
        if not shard_results:
            raise ValueError("At least one shard result is required")
        total_draws = sum(shard.draws for shard in shard_results)
        self._validate_inputs(total_draws)

        pick_counters: list[Counter[str]] = [Counter() for _ in self.draft_order]
        prospect_counter: Counter[str] = Counter()
        prospect_team_counters: dict[str, Counter[str]] = defaultdict(Counter)
        milestone_values: dict[str, list[_MilestoneValue]] = {
            milestone.id: [] for milestone in self._milestones
        }

        for shard in sorted(shard_results, key=lambda result: result.shard_index):
            if len(shard.pick_counts) != len(self.draft_order):
                raise ValueError(
                    "Shard pick_counts length must match the draft order length"
                )
            for index, counts in enumerate(shard.pick_counts):
                pick_counters[index].update(counts)
            prospect_counter.update(shard.prospect_counts)
            for prospect_id, team_counts in shard.prospect_team_counts.items():
                prospect_team_counters[prospect_id].update(team_counts)
            for milestone in self._milestones:
                milestone_values[milestone.id].extend(
                    shard.milestone_values.get(milestone.id, [])
                )

        picks = self._build_pick_distributions(pick_counters, total_draws)
        assigned_picks = self._build_assigned_picks(
            pick_counters,
            prospect_counter,
            total_draws,
        )
        milestones = self._attach_board_answers(
            self._build_milestones(milestone_values),
            assigned_picks,
        )
        return TwinReport(
            config=replace(self.config, draws=total_draws),
            picks=picks,
            assigned_picks=assigned_picks,
            board=self._build_board(
                prospect_counter,
                prospect_team_counters,
                total_draws,
            ),
            milestones=milestones,
            low_confidence_picks=[pick.pick for pick in picks if pick.low_confidence],
        )

    def _validate_inputs(self, draws: int) -> None:
        if draws <= 0:
            raise ValueError("SimulationConfig.draws must be positive")
        if not self.prospects:
            raise ValueError("At least one prospect is required")
        if not self.draft_order:
            raise ValueError("Draft order is required")
        if len(self.prospects) < len(self.draft_order):
            raise ValueError("At least one available prospect is required for every pick")

    def _simulate_one(
        self,
        rng: random.Random,
        capture_trace: bool = False,
    ) -> list[str]:
        weights = self._sample_weights(rng)
        need_index = self._sample_need_index(rng)
        mock_index = self._sample_mock_index(rng)
        predictor = DraftPredictor(weights)
        max_rank = max(prospect.consensus_rank for prospect in self.prospects)
        available = {prospect.prospect_id: prospect for prospect in self.prospects}
        selected: list[str] = []
        trace_picks: list[dict[str, object]] = []

        for team in self.draft_order:
            scored = [
                self._score_available_prospect(
                    predictor,
                    prospect,
                    team,
                    max_rank,
                    need_index,
                    mock_index,
                    rng,
                    weights,
                )
                for prospect in available.values()
            ]
            scored.sort(
                key=lambda row: (float(row["score"]), -int(row["consensus_rank"])),
                reverse=True,
            )
            if capture_trace:
                trace_picks.append(
                    {
                        "pick": team.pick,
                        "team": team.abbreviation,
                        "top_candidates": [
                            {
                                "prospect_id": row["prospect_id"],
                                "prospect": row["name"],
                                "score": round(float(row["score"]), 4),
                                "preference": row.get("preference_breakdown", {}),
                            }
                            for row in scored[:5]
                        ],
                    }
                )
            winner_id = self._choose_candidate(scored[: max(1, self.config.top_k)], rng)
            selected.append(winner_id)
            available.pop(winner_id)

        if capture_trace:
            self.preference_trace = trace_picks
        return selected

    def _sample_weights(self, rng: random.Random) -> ModelWeights:
        raw = {
            "board": self.weights.board * math.exp(rng.gauss(0.0, self.config.weight_jitter)),
            "pick_slot": self.weights.pick_slot
            * math.exp(rng.gauss(0.0, self.config.weight_jitter)),
            "team_need": self.weights.team_need
            * math.exp(rng.gauss(0.0, self.config.weight_jitter)),
            "mock_signal": self.weights.mock_signal
            * math.exp(rng.gauss(0.0, self.config.weight_jitter)),
        }
        total = sum(raw.values())
        return ModelWeights(
            board=raw["board"] / total,
            pick_slot=raw["pick_slot"] / total,
            team_need=raw["team_need"] / total,
            mock_signal=raw["mock_signal"] / total,
        )

    def _sample_need_index(self, rng: random.Random) -> dict[str, dict[str, float]]:
        index: dict[str, dict[str, float]] = defaultdict(dict)
        for need in self.team_needs:
            multiplier = max(0.0, rng.gauss(1.0, self.config.need_jitter))
            index[need.abbreviation][need.position] = _clamp(need.weight * multiplier)
        return index

    def _sample_mock_index(self, rng: random.Random) -> dict[str, dict[str, float]]:
        index: dict[str, dict[str, float]] = defaultdict(dict)
        for signal in self.mock_signals:
            multiplier = max(0.0, rng.gauss(1.0, self.config.signal_jitter))
            current = index[signal.abbreviation].get(signal.prospect_id, 0.0)
            index[signal.abbreviation][signal.prospect_id] = max(
                current,
                _clamp(signal.signal_strength * multiplier),
            )
        return index

    def _score_available_prospect(
        self,
        predictor: DraftPredictor,
        prospect: Prospect,
        team: Team,
        max_rank: int,
        need_index: dict[str, dict[str, float]],
        mock_index: dict[str, dict[str, float]],
        rng: random.Random,
        weights: ModelWeights,
    ) -> dict[str, object]:
        components = predictor._score_prospect(
            prospect=prospect,
            pick_number=team.pick,
            team_abbr=team.abbreviation,
            max_rank=max_rank,
            need_index=need_index,
            mock_index=mock_index,
        )
        board_eff = _clamp(
            float(components["board_score"]) + rng.gauss(0.0, self.config.board_jitter)
        )
        dossier = None if self.dossiers is None else self.dossiers.get(team.abbreviation)
        llm_raw_delta, llm_score_adjustment = self._gm_adjustment(
            team.abbreviation,
            str(components["prospect_id"]),
        )
        if dossier is None:
            score = (
                weights.board * (0.78 * board_eff + 0.22 * float(components["production_score"]))
                + weights.pick_slot * float(components["slot_score"])
                + weights.team_need * float(components["need_score"])
                + weights.mock_signal * float(components["mock_score"])
            )
            adjusted_score = _clamp(score + llm_score_adjustment)
            return {
                "prospect_id": components["prospect_id"],
                "name": components["name"],
                "consensus_rank": components["consensus_rank"],
                "score": adjusted_score,
                "preference_breakdown": {
                    "score_before_llm": round(_clamp(score), 4),
                    "llm_raw_delta": round(llm_raw_delta, 4),
                    "llm_weight": _GM_PREFERENCE_WEIGHT,
                    "llm_delta": round(llm_score_adjustment, 4),
                    "score_after_llm": round(adjusted_score, 4),
                },
            }

        preference_components = dict(components)
        preference_components["board_score"] = board_eff
        preference_components["pick_number"] = team.pick
        score, breakdown = preference_score(dossier, prospect, preference_components)
        adjusted_score = _clamp(score + llm_score_adjustment)
        breakdown["score_before_llm"] = score
        breakdown["llm_raw_delta"] = llm_raw_delta
        breakdown["llm_weight"] = _GM_PREFERENCE_WEIGHT
        breakdown["llm_delta"] = llm_score_adjustment
        breakdown["score_after_llm"] = adjusted_score
        rounded_breakdown = {
            key: round(value, 4) if isinstance(value, float) else value
            for key, value in breakdown.items()
        }
        return {
            "prospect_id": components["prospect_id"],
            "name": components["name"],
            "consensus_rank": components["consensus_rank"],
            "score": adjusted_score,
            "preference_breakdown": rounded_breakdown,
        }

    def _gm_adjustment(self, abbreviation: str, prospect_id: str) -> tuple[float, float]:
        raw_delta = self.gm_preferences.get(abbreviation, {}).get(prospect_id, 0.0)
        return raw_delta, raw_delta * _GM_PREFERENCE_WEIGHT

    def _choose_candidate(
        self,
        candidates: list[dict[str, object]],
        rng: random.Random,
    ) -> str:
        if not candidates:
            raise ValueError("No candidates available for simulated pick")
        if self.config.temperature <= 1e-6:
            return str(candidates[0]["prospect_id"])

        temperature = max(self.config.temperature, 1e-12)
        max_score = max(float(candidate["score"]) for candidate in candidates)
        weights = [
            math.exp((float(candidate["score"]) - max_score) / temperature)
            for candidate in candidates
        ]
        total = sum(weights)
        draw = rng.random()
        cumulative = 0.0
        for candidate, weight in zip(candidates, weights, strict=True):
            cumulative += weight / total
            if draw <= cumulative:
                return str(candidate["prospect_id"])
        return str(candidates[-1]["prospect_id"])

    def _build_pick_distributions(
        self,
        pick_counters: list[Counter[str]],
        draws: int,
    ) -> list[PickDistribution]:
        distributions: list[PickDistribution] = []
        for team, counter in zip(self.draft_order, pick_counters, strict=True):
            ranked = sorted(
                counter.items(),
                key=lambda item: (-item[1], self._prospect_rank[item[0]], item[0]),
            )
            most_likely_id, most_likely_count = ranked[0]
            most_likely = self._prospect_index[most_likely_id]
            probability = most_likely_count / draws
            distributions.append(
                PickDistribution(
                    pick=team.pick,
                    team=team.team,
                    abbreviation=team.abbreviation,
                    most_likely_id=most_likely_id,
                    most_likely_name=most_likely.name,
                    probability=probability,
                    distribution=[
                        CandidateProb(
                            prospect_id=prospect_id,
                            name=self._prospect_index[prospect_id].name,
                            probability=count / draws,
                        )
                        for prospect_id, count in ranked[:5]
                    ],
                    low_confidence=probability < self.config.low_confidence_threshold,
                )
            )
        return distributions

    def _build_assigned_picks(
        self,
        pick_counters: list[Counter[str]],
        prospect_counter: Counter[str],
        draws: int,
    ) -> list[AssignedPick]:
        prospect_ids = self._assignment_candidate_ids(pick_counters, prospect_counter)
        weight_matrix = [
            [counter.get(prospect_id, 0) for prospect_id in prospect_ids]
            for counter in pick_counters
        ]
        assignment = _max_weight_assignment(weight_matrix)

        assigned: list[AssignedPick] = []
        for team, counter, column_index in zip(
            self.draft_order,
            pick_counters,
            assignment,
            strict=True,
        ):
            prospect_id = prospect_ids[column_index]
            prospect = self._prospect_index[prospect_id]
            assigned.append(
                AssignedPick(
                    pick=team.pick,
                    team=team.team,
                    abbreviation=team.abbreviation,
                    prospect_id=prospect_id,
                    prospect_name=prospect.name,
                    marginal_probability=counter.get(prospect_id, 0) / draws,
                )
            )
        return assigned

    def _assignment_candidate_ids(
        self,
        pick_counters: list[Counter[str]],
        prospect_counter: Counter[str],
    ) -> list[str]:
        """Return the first-round probability pool used for unique pick assignment."""
        marginal_counter: Counter[str] = Counter()
        for counter in pick_counters:
            marginal_counter.update(counter)

        return sorted(
            self._prospect_index,
            key=lambda prospect_id: (
                -prospect_counter[prospect_id],
                -marginal_counter[prospect_id],
                self._prospect_rank[prospect_id],
                prospect_id,
            ),
        )[: len(self.draft_order)]

    def _build_board(
        self,
        prospect_counter: Counter[str],
        prospect_team_counters: dict[str, Counter[str]],
        draws: int,
    ) -> list[ProspectOutlook]:
        board: list[ProspectOutlook] = []
        for prospect in self.prospects:
            team_ranked = sorted(
                prospect_team_counters[prospect.prospect_id].items(),
                key=lambda item: (
                    -item[1],
                    self._team_order.get(item[0], len(self._team_order)),
                    item[0],
                ),
            )
            board.append(
                ProspectOutlook(
                    prospect_id=prospect.prospect_id,
                    name=prospect.name,
                    first_round_probability=prospect_counter[prospect.prospect_id]
                    / draws,
                    team_probabilities=[
                        TeamProb(
                            abbreviation=team_abbr,
                            probability=count / draws,
                        )
                        for team_abbr, count in team_ranked[:5]
                    ],
                )
            )
        return sorted(
            board,
            key=lambda outlook: (
                -outlook.first_round_probability,
                self._prospect_rank[outlook.prospect_id],
                outlook.prospect_id,
            ),
        )

    def _attach_board_answers(
        self,
        milestones: list[MilestoneAnswer],
        assigned_picks: list[AssignedPick],
    ) -> list[MilestoneAnswer]:
        """Fill each milestone's board-consistent answer from the assigned board.

        The submitted answer card and the public board must agree, so milestone
        answers are recomputed on the single Hungarian-assigned board. The
        ``answer_display``/``expected``/P10-P90 distribution view is preserved
        untouched for the audit trail.
        """
        board_ids = [
            pick.prospect_id
            for pick in sorted(assigned_picks, key=lambda item: item.pick)
        ]
        definitions = {definition.id: definition for definition in self._milestones}
        enriched: list[MilestoneAnswer] = []
        for milestone in milestones:
            definition = definitions.get(milestone.id)
            if definition is None:
                enriched.append(milestone)
                continue
            enriched.append(
                replace(
                    milestone,
                    board_answer_display=self._board_answer_display(
                        definition, board_ids
                    ),
                )
            )
        return enriched

    def _board_answer_display(
        self, definition: _MilestoneDefinition, board_ids: list[str]
    ) -> str:
        value = definition.calculator(board_ids)
        if definition.answer_kind == "category":
            return value if isinstance(value, str) else ""
        if value is None:
            return ""
        return str(_round_half_up(float(value)))

    def _build_milestones(
        self,
        milestone_values: dict[str, list[_MilestoneValue]],
    ) -> list[MilestoneAnswer]:
        answers: list[MilestoneAnswer] = []
        for milestone in self._milestones:
            values = milestone_values[milestone.id]
            if milestone.answer_kind == "category":
                category_values = [str(value) for value in values]
                answer, confidence = _most_common_category(category_values)
                answers.append(
                    MilestoneAnswer(
                        id=milestone.id,
                        question=milestone.question,
                        status="answered",
                        answer_kind=milestone.answer_kind,
                        answer_display=answer,
                        expected=None,
                        p10=None,
                        p90=None,
                        confidence=confidence,
                        detail=milestone.detail,
                    )
                )
                continue

            numeric_values = [float(value) for value in values]
            p10: float | None = None
            p90: float | None = None
            if len(numeric_values) >= 2:
                deciles = statistics.quantiles(numeric_values, n=10)
                p10 = deciles[0]
                p90 = deciles[8]
            expected = statistics.fmean(numeric_values)
            answers.append(
                MilestoneAnswer(
                    id=milestone.id,
                    question=milestone.question,
                    status="answered",
                    answer_kind=milestone.answer_kind,
                    answer_display=str(_round_half_up(expected)),
                    expected=expected,
                    p10=p10,
                    p90=p90,
                    confidence=None,
                    detail=milestone.detail,
                )
            )
        return answers

    def _build_milestone_definitions(self) -> list[_MilestoneDefinition]:
        return [
            _MilestoneDefinition(
                id="Q1",
                question=(
                    "第 4–14 顺位（共11人）中，臂展减赤脚身高 ≥ 5 英寸"
                    "（约12.7cm）的“超长臂展”球员有几人？"
                ),
                answer_kind="count",
                detail=(
                    "Counts picks 4-14 where both wingspan_in and barefoot_height_in are "
                    "available and wingspan_in - barefoot_height_in >= 5."
                ),
                calculator=self._q1_wingspan_minus_height,
            ),
            _MilestoneDefinition(
                id="Q2",
                question="训练营“助跑最大弹跳”排名前 3 的球员中，有几人在首轮被选中？",
                answer_kind="count",
                detail=(
                    "Counts selected first-round prospects in the fixed full-pool top 3 by "
                    "max_vertical_in, sorted by value descending then prospect_id ascending."
                ),
                calculator=self._q2_top_max_vertical_selected,
            ),
            _MilestoneDefinition(
                id="Q3",
                question="首轮 30 人中，主打位置为中锋（C）的球员总数？",
                answer_kind="count",
                detail="Counts selected first-round prospects where is_center is true.",
                calculator=self._q3_center_count,
            ),
            _MilestoneDefinition(
                id="Q4",
                question="第 4–30 顺位中，第一个被选中的中锋落在第几顺位？",
                answer_kind="pick",
                detail=(
                    "Returns the first draft-order pick from 4-30 with is_center true; "
                    "returns 0 when no such prospect is selected."
                ),
                calculator=self._q4_first_center_pick,
            ),
            _MilestoneDefinition(
                id="Q5",
                question="首轮 30 人中，国际球员（非美国本土成长）总数？",
                answer_kind="count",
                detail="Counts selected first-round prospects where is_international is true.",
                calculator=self._q5_international_count,
            ),
            _MilestoneDefinition(
                id="Q6",
                question="本届首轮贡献球员最多的大学 / 培养机构是哪一所/家？",
                answer_kind="category",
                detail=(
                    "Finds each simulation's most common non-empty school among selected "
                    "first-round prospects, then reports the most frequent simulation mode."
                ),
                calculator=self._q6_school_mode,
            ),
            _MilestoneDefinition(
                id="Q7",
                question="训练营“手掌长度”排名前 5 的球员中，有几人在首轮被选中？",
                answer_kind="count",
                detail=(
                    "Counts selected first-round prospects in the fixed full-pool top 5 by "
                    "hand_length_in, sorted by value descending then prospect_id ascending."
                ),
                calculator=self._q7_top_hand_length_selected,
            ),
        ]

    def _top_n_prospect_ids(self, field_name: str, limit: int) -> frozenset[str]:
        candidates: list[tuple[float, str]] = []
        for prospect in self.prospects:
            value = getattr(prospect, field_name)
            if value is not None:
                candidates.append((float(value), prospect.prospect_id))
        candidates.sort(key=lambda row: (-row[0], row[1]))
        return frozenset(prospect_id for _, prospect_id in candidates[:limit])

    def _q1_wingspan_minus_height(self, selected_ids: list[str]) -> float:
        count = 0
        for prospect_id, team in zip(selected_ids, self.draft_order, strict=True):
            if not 4 <= team.pick <= 14:
                continue
            prospect = self._prospect_index[prospect_id]
            if prospect.barefoot_height_in is None:
                continue
            if prospect.wingspan_in - prospect.barefoot_height_in >= 5:
                count += 1
        return float(count)

    def _q2_top_max_vertical_selected(self, selected_ids: list[str]) -> float:
        return float(
            sum(1 for prospect_id in selected_ids if prospect_id in self._top_max_vertical_ids)
        )

    def _q3_center_count(self, selected_ids: list[str]) -> float:
        return float(
            sum(1 for prospect_id in selected_ids if self._prospect_index[prospect_id].is_center)
        )

    def _q4_first_center_pick(self, selected_ids: list[str]) -> float:
        for prospect_id, team in zip(selected_ids, self.draft_order, strict=True):
            if 4 <= team.pick <= 30 and self._prospect_index[prospect_id].is_center:
                return float(team.pick)
        return 0.0

    def _q5_international_count(self, selected_ids: list[str]) -> float:
        return float(
            sum(
                1
                for prospect_id in selected_ids
                if self._prospect_index[prospect_id].is_international
            )
        )

    def _q6_school_mode(self, selected_ids: list[str]) -> str:
        school_counts: Counter[str] = Counter(
            school
            for prospect_id in selected_ids
            if (school := self._prospect_index[prospect_id].school.strip())
        )
        if not school_counts:
            return ""
        return sorted(school_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]

    def _q7_top_hand_length_selected(self, selected_ids: list[str]) -> float:
        return float(
            sum(1 for prospect_id in selected_ids if prospect_id in self._top_hand_length_ids)
        )


def simulate_shard(
    shard_index: int,
    draws: int,
    prospects: list[Prospect],
    draft_order: list[Team],
    team_needs: list[TeamNeed],
    mock_signals: list[MockSignal],
    config: SimulationConfig,
    weights: ModelWeights | None = None,
    dossiers: dict[str, TeamDossier] | None = None,
    gm_preferences: dict[str, dict[str, float]] | None = None,
) -> ShardResult:
    """Run one deterministic shard without requiring callers to manage the class."""
    return MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=team_needs,
        mock_signals=mock_signals,
        config=config,
        weights=weights,
        dossiers=dossiers,
        gm_preferences=gm_preferences,
    ).simulate_shard(shard_index, draws)


def aggregate_shards(
    shard_results: list[ShardResult],
    prospects: list[Prospect],
    draft_order: list[Team],
    config: SimulationConfig,
) -> TwinReport:
    """Aggregate raw shard outputs into a full Milestone-Aware Draft Twin report."""
    return MonteCarloDraftTwin(
        prospects=prospects,
        draft_order=draft_order,
        team_needs=[],
        mock_signals=[],
        config=config,
    ).aggregate_shards(shard_results)


def _normalize_gm_preferences(
    gm_preferences: Mapping[str, Mapping[str, object]] | None,
) -> dict[str, dict[str, float]]:
    if not isinstance(gm_preferences, Mapping):
        return {}

    normalized: dict[str, dict[str, float]] = {}
    for abbreviation, raw_adjustments in gm_preferences.items():
        if not isinstance(raw_adjustments, Mapping):
            continue
        adjustments: dict[str, float] = {}
        for prospect_id, delta in raw_adjustments.items():
            try:
                adjustments[str(prospect_id)] = _clamp(
                    float(delta),
                    -_GM_DELTA_LIMIT,
                    _GM_DELTA_LIMIT,
                )
            except (TypeError, ValueError):
                continue
        if adjustments:
            normalized[str(abbreviation)] = dict(sorted(adjustments.items()))
    return dict(sorted(normalized.items()))


def _sorted_count_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _round_half_up(value: float) -> int:
    return int(math.floor(value + 0.5))


def _most_common_category(values: list[str]) -> tuple[str, float]:
    if not values:
        return "", 0.0
    ranked = sorted(Counter(values).items(), key=lambda item: (-item[1], item[0]))
    answer, count = ranked[0]
    return answer, count / len(values)
