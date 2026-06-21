from __future__ import annotations

from collections import defaultdict

from draftcode.schemas import DraftPick, MockSignal, ModelWeights, Prospect, Team, TeamNeed


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class DraftPredictor:
    """Sequential draft simulator with auditable, weighted decisions."""

    def __init__(self, weights: ModelWeights | None = None) -> None:
        self.weights = weights or ModelWeights()

    def predict(
        self,
        prospects: list[Prospect],
        draft_order: list[Team],
        team_needs: list[TeamNeed],
        mock_signals: list[MockSignal] | None = None,
    ) -> tuple[list[DraftPick], dict[str, object]]:
        if not prospects:
            raise ValueError("At least one prospect is required")
        if not draft_order:
            raise ValueError("Draft order is required")

        max_rank = max(prospect.consensus_rank for prospect in prospects)
        need_index = self._index_needs(team_needs)
        mock_index = self._index_mock_signals(mock_signals or [])
        available = {prospect.prospect_id: prospect for prospect in prospects}
        picks: list[DraftPick] = []
        trace: dict[str, object] = {"picks": []}

        for team in sorted(draft_order, key=lambda row: row.pick):
            scored = [
                self._score_prospect(
                    prospect=prospect,
                    pick_number=team.pick,
                    team_abbr=team.abbreviation,
                    max_rank=max_rank,
                    need_index=need_index,
                    mock_index=mock_index,
                )
                for prospect in available.values()
            ]
            scored.sort(key=lambda row: (row["score"], -row["consensus_rank"]), reverse=True)
            winner = scored[0]
            prospect = available.pop(str(winner["prospect_id"]))
            confidence = self._confidence(scored)
            pick = DraftPick(
                pick=team.pick,
                team=team.team,
                abbreviation=team.abbreviation,
                prospect_id=prospect.prospect_id,
                prospect_name=prospect.name,
                score=round(float(winner["score"]), 4),
                confidence=confidence,
                reason=self._reason(team, prospect, winner),
            )
            picks.append(pick)
            trace["picks"].append(
                {
                    "pick": team.pick,
                    "team": team.abbreviation,
                    "selected": prospect.name,
                    "top_candidates": [
                        {
                            "prospect": row["name"],
                            "score": round(float(row["score"]), 4),
                            "board": round(float(row["board_score"]), 4),
                            "slot": round(float(row["slot_score"]), 4),
                            "need": round(float(row["need_score"]), 4),
                            "mock": round(float(row["mock_score"]), 4),
                        }
                        for row in scored[:5]
                    ],
                }
            )

        return picks, trace

    def _score_prospect(
        self,
        prospect: Prospect,
        pick_number: int,
        team_abbr: str,
        max_rank: int,
        need_index: dict[str, dict[str, float]],
        mock_index: dict[str, dict[str, float]],
    ) -> dict[str, float | str | int]:
        board_score = 1 - ((prospect.consensus_rank - 1) / max(max_rank - 1, 1))
        slot_score = 1 / (1 + abs(prospect.consensus_rank - pick_number) / 8)
        need_score = need_index.get(team_abbr, {}).get(prospect.primary_position, 0.25)
        mock_score = mock_index.get(team_abbr, {}).get(prospect.prospect_id, 0.0)
        production_score = self._production_score(prospect)

        score = (
            self.weights.board * (0.78 * board_score + 0.22 * production_score)
            + self.weights.pick_slot * slot_score
            + self.weights.team_need * need_score
            + self.weights.mock_signal * mock_score
        )

        return {
            "prospect_id": prospect.prospect_id,
            "name": prospect.name,
            "consensus_rank": prospect.consensus_rank,
            "board_score": board_score,
            "slot_score": slot_score,
            "need_score": need_score,
            "mock_score": mock_score,
            "production_score": production_score,
            "score": score,
        }

    @staticmethod
    def _production_score(prospect: Prospect) -> float:
        shooting = _clamp((prospect.true_shooting_pct - 0.48) / 0.18)
        creation = _clamp(prospect.assist_rate / 35)
        play_finishing = _clamp(prospect.usage_rate / 32)
        defense = _clamp(prospect.stock_rate / 6)
        rebounding = _clamp(prospect.rebound_rate / 22)
        return (
            0.28 * shooting
            + 0.22 * creation
            + 0.2 * play_finishing
            + 0.18 * defense
            + 0.12 * rebounding
        )

    @staticmethod
    def _index_needs(team_needs: list[TeamNeed]) -> dict[str, dict[str, float]]:
        index: dict[str, dict[str, float]] = defaultdict(dict)
        for need in team_needs:
            index[need.abbreviation][need.position] = _clamp(need.weight)
        return index

    @staticmethod
    def _index_mock_signals(mock_signals: list[MockSignal]) -> dict[str, dict[str, float]]:
        index: dict[str, dict[str, float]] = defaultdict(dict)
        for signal in mock_signals:
            current = index[signal.abbreviation].get(signal.prospect_id, 0.0)
            index[signal.abbreviation][signal.prospect_id] = max(current, _clamp(signal.signal_strength))
        return index

    @staticmethod
    def _confidence(scored: list[dict[str, float | str | int]]) -> float:
        if len(scored) == 1:
            return 1.0
        gap = float(scored[0]["score"]) - float(scored[1]["score"])
        return round(_clamp(0.5 + gap * 2.8), 4)

    @staticmethod
    def _reason(team: Team, prospect: Prospect, score_row: dict[str, float | str | int]) -> str:
        return (
            f"{team.abbreviation} selects {prospect.name}: "
            f"board={float(score_row['board_score']):.2f}, "
            f"slot-fit={float(score_row['slot_score']):.2f}, "
            f"need={float(score_row['need_score']):.2f}, "
            f"market-signal={float(score_row['mock_score']):.2f}; "
            f"profile={prospect.primary_position}/{prospect.archetype}."
        )
