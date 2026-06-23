from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from draftcode.dossier import TeamDossier
from draftcode.schemas import Prospect


def preference_score(
    dossier: TeamDossier,
    prospect: Prospect,
    components: Mapping[str, Any],
) -> tuple[float, dict[str, float | str]]:
    """Score one team-prospect edge from talent, need, persona, and market signals."""
    weights = _persona_weights(dossier.gm_persona.philosophy)
    talent = _talent_score(prospect, components)
    need_fit = _component_float(
        components,
        "need_score",
        dossier.roster_needs.get(prospect.primary_position, 0.25),
    )
    persona_fit = _persona_fit(dossier, prospect, components)
    market = _market_score(prospect, components)
    money = _odds_score(prospect, components)

    score = (
        weights["talent"] * talent
        + weights["need"] * need_fit
        + weights["persona"] * persona_fit
        + weights["market"] * market
        + weights["money"] * money
    )
    breakdown: dict[str, float | str] = {
        "score": _clamp(score),
        "talent": talent,
        "need_fit": need_fit,
        "persona_fit": persona_fit,
        "market": market,
        "money": money,
        "w_talent": weights["talent"],
        "w_need": weights["need"],
        "w_persona": weights["persona"],
        "w_market": weights["market"],
        "w_money": weights["money"],
        "philosophy": dossier.gm_persona.philosophy,
        "risk_tolerance": dossier.gm_persona.risk_tolerance,
        "intl_openness": dossier.gm_persona.intl_openness,
    }
    return float(breakdown["score"]), breakdown


def _persona_weights(philosophy: str) -> dict[str, float]:
    # `money` is an ADDITIVE money-signal weight (de-vigged odds). It contributes
    # nothing when a prospect has no odds_signal (top-of-board only), so no-odds
    # runs are byte-identical; existing weights are intentionally not rebalanced.
    if philosophy == "BPA":
        return {"talent": 0.52, "need": 0.14, "persona": 0.20, "market": 0.14, "money": 0.12}
    if philosophy == "NEED":
        return {"talent": 0.30, "need": 0.36, "persona": 0.20, "market": 0.14, "money": 0.12}
    return {"talent": 0.40, "need": 0.24, "persona": 0.22, "market": 0.14, "money": 0.12}


def _talent_score(prospect: Prospect, components: Mapping[str, Any]) -> float:
    board = _component_float(components, "board_score", 0.0)
    production = _component_float(components, "production_score", 0.5)
    model_signal = prospect.talent_signal if prospect.talent_signal is not None else None
    if model_signal is None and prospect.fused_score is not None:
        model_signal = prospect.fused_score
    if model_signal is None:
        return _clamp(0.78 * board + 0.22 * production)
    return _clamp(0.55 * board + 0.25 * float(model_signal) + 0.20 * production)


def _market_score(prospect: Prospect, components: Mapping[str, Any]) -> float:
    mock = _component_float(components, "mock_score", 0.0)
    market_signal = prospect.market_signal if prospect.market_signal is not None else 0.0
    return _clamp(max(mock, float(market_signal)))


def _odds_score(prospect: Prospect, components: Mapping[str, Any]) -> float:
    """De-vigged money signal (0 when the prospect has no odds market)."""
    explicit = _component_float(components, "odds_score", 0.0)
    signal = prospect.odds_signal if prospect.odds_signal is not None else 0.0
    return _clamp(max(explicit, float(signal)))


def _persona_fit(
    dossier: TeamDossier,
    prospect: Prospect,
    components: Mapping[str, Any],
) -> float:
    archetype = _archetype_fit(dossier, prospect)
    risk = _risk_fit(dossier.gm_persona.risk_tolerance, prospect, components)
    intl = dossier.gm_persona.intl_openness if prospect.is_international else 0.58
    return _clamp(0.52 * archetype + 0.30 * risk + 0.18 * intl)


def _archetype_fit(dossier: TeamDossier, prospect: Prospect) -> float:
    tags = _prospect_tags(prospect)
    preferences = dossier.gm_persona.archetype_pref
    matches = sum(1 for preference in preferences if preference in tags)
    if matches == 0:
        return 0.38
    return _clamp(0.48 + 0.52 * (matches / len(preferences)))


def _prospect_tags(prospect: Prospect) -> frozenset[str]:
    position = prospect.primary_position.lower()
    tags = {
        position,
        prospect.archetype.lower(),
        {"g": "guard", "w": "wing", "b": "big"}.get(position, position),
    }
    archetype_words = prospect.archetype.lower().replace("-", " ").split()
    tags.update(archetype_words)
    if prospect.age <= 19.5:
        tags.add("upside")
        tags.add("young")
    if prospect.true_shooting_pct >= 0.60:
        tags.add("shooter")
        tags.add("spacing")
    if prospect.assist_rate >= 22:
        tags.add("creator")
        tags.add("guard")
    if prospect.stock_rate >= 4.0 or prospect.wingspan_in - prospect.height_in >= 5.0:
        tags.add("defense")
        tags.add("length")
    if prospect.rebound_rate >= 18:
        tags.add("rebounder")
        tags.add("big")
    if prospect.is_center:
        tags.add("center")
        tags.add("big")
    if prospect.is_international:
        tags.add("international")
    return frozenset(tags)


def _risk_fit(
    risk_tolerance: str,
    prospect: Prospect,
    components: Mapping[str, Any],
) -> float:
    upside = _upside_score(prospect)
    floor = _floor_score(prospect, components)
    if risk_tolerance == "high":
        return _clamp(0.72 * upside + 0.28 * floor)
    if risk_tolerance == "low":
        return _clamp(0.28 * upside + 0.72 * floor)
    return _clamp(0.50 * upside + 0.50 * floor)


def _upside_score(prospect: Prospect) -> float:
    youth = _clamp((23.5 - prospect.age) / 5.0)
    length = _clamp((prospect.wingspan_in - prospect.height_in + 1.0) / 8.0)
    vertical = 0.5
    if prospect.max_vertical_in is not None:
        vertical = _clamp((prospect.max_vertical_in - 28.0) / 16.0)
    board = 1.0
    if prospect.consensus_rank > 1:
        board = _clamp(1 - ((prospect.consensus_rank - 1) / 79))
    return _clamp(0.34 * youth + 0.24 * length + 0.20 * vertical + 0.22 * board)


def _floor_score(prospect: Prospect, components: Mapping[str, Any]) -> float:
    production = _component_float(components, "production_score", 0.5)
    shooting = _clamp((prospect.true_shooting_pct - 0.50) / 0.16)
    market = _market_score(prospect, components)
    age_floor = _clamp((prospect.age - 18.0) / 5.0)
    return _clamp(0.42 * production + 0.22 * shooting + 0.20 * market + 0.16 * age_floor)


def _component_float(
    components: Mapping[str, Any],
    key: str,
    default: float,
) -> float:
    value = components.get(key, default)
    try:
        return _clamp(float(value))
    except (TypeError, ValueError):
        return _clamp(default)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))
