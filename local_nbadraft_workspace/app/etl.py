from __future__ import annotations

import argparse
from datetime import date
from difflib import SequenceMatcher
import math
from pathlib import Path
import re
import uuid

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, create_schema
from app.models import CombineMeasurement, DraftBoard, ManualPlayerOverride, Player
from app.snapshot import _stable_hash, normalize_mode


USA_VALUES = {"usa", "us", "u s a", "united states", "united states of america", "america"}

COLUMN_ALIASES = {
    "name": ["name", "player", "playername", "prospect", "prospectname"],
    "position": ["position", "pos"],
    "country": ["country", "nationality", "nation"],
    "school": ["school", "college", "team", "club"],
    "pick_number": ["pick", "picknumber", "rank", "ranking", "boardrank", "mockpick"],
    "board_type": ["boardtype", "mode", "type"],
    "height_in": ["height", "heightin", "heightinch", "heightinches"],
    "wingspan_in": ["wingspan", "wingspanin", "wingspaninch", "wingspaninches"],
    "weight_lbs": ["weight", "weightlbs", "weightpounds"],
    "vertical_max_in": ["vertical", "maxvertical", "verticalmax", "verticalmaxin"],
    "sprint_sec": ["sprint", "sprintsec", "threesprint", "threequartersprint", "laneagility"],
    "hand_length_in": ["handlength", "handlengthin", "handlengthinches"],
    "hand_width_in": ["handwidth", "handwidthin", "handwidthinches"],
}


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9\s]", "", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def clean_cell(value: object) -> object | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def get_value(row: pd.Series, columns_by_norm: dict[str, str], field: str) -> object | None:
    for alias in COLUMN_ALIASES[field]:
        column = columns_by_norm.get(alias)
        if column is not None:
            return clean_cell(row[column])
    return None


def parse_float(value: object | None) -> float | None:
    value = clean_cell(value)
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group(0)) if match else None


def parse_inches(value: object | None, *, height_like: bool) -> float | None:
    value = clean_cell(value)
    if value is None:
        return None
    if isinstance(value, int | float):
        numeric = float(value)
        if height_like and numeric <= 8.5:
            return numeric * 12
        return numeric

    raw = str(value).lower().replace("feet", "ft").replace("inches", "in")
    feet_inches = re.search(r"(\d+)\s*(?:'|ft|-)\s*(\d+(?:\.\d+)?)?", raw)
    if feet_inches and height_like:
        feet = float(feet_inches.group(1))
        inches = float(feet_inches.group(2) or 0)
        if feet <= 8:
            return feet * 12 + inches

    numeric = parse_float(raw)
    if numeric is not None and height_like and numeric <= 8.5:
        return numeric * 12
    return numeric


def parse_int(value: object | None) -> int | None:
    numeric = parse_float(value)
    return int(numeric) if numeric is not None else None


def is_international(country: str | None) -> bool:
    if not country:
        return False
    return normalize_name(country) not in USA_VALUES


def position_bucket(position: str | None) -> str | None:
    if not position:
        return None
    normalized = position.strip().upper()
    if "CENTER" in normalized:
        return "C"
    tokens = [token for token in re.split(r"[\s,/-]+", normalized) if token]
    if "C" in tokens:
        return "C"
    return tokens[0] if tokens else normalized


def resolve_player(session: Session, name: str) -> Player:
    name_norm = normalize_name(name)

    exact = session.scalar(select(Player).where(Player.name_norm == name_norm))
    if exact is not None:
        return exact

    players = list(session.scalars(select(Player)).all())
    best_player: Player | None = None
    best_score = 0.0
    for player in players:
        score = SequenceMatcher(None, name_norm, player.name_norm).ratio()
        if score > best_score:
            best_player = player
            best_score = score
    if best_player is not None and best_score > 0.92:
        return best_player

    override = session.scalar(select(ManualPlayerOverride).where(ManualPlayerOverride.raw_name_norm == name_norm))
    if override is not None:
        if override.player_id is not None:
            player = session.get(Player, override.player_id)
            if player is not None:
                return player
        if override.canonical_name_norm:
            player = session.scalar(select(Player).where(Player.name_norm == override.canonical_name_norm))
            if player is not None:
                return player

    player = Player(
        id=uuid.uuid4(),
        name=name.strip(),
        name_norm=name_norm,
        is_international=False,
    )
    session.add(player)
    session.flush()
    return player


def update_player_profile(
    player: Player,
    *,
    name: str,
    position: str | None,
    country: str | None,
    school: str | None,
) -> None:
    player.name = player.name or name.strip()
    if position:
        player.position = str(position).strip()
        player.position_bucket = position_bucket(player.position)
    if country:
        player.country = str(country).strip()
        player.is_international = is_international(player.country)
    if school:
        player.school = str(school).strip()


def load_excel(
    session: Session,
    path: Path,
    *,
    snapshot_date: date,
    source: str,
    board_type: str,
    sheet_name: str | int | None = 0,
) -> dict[str, int]:
    mode = normalize_mode(board_type)
    frame = pd.read_excel(path, sheet_name=sheet_name)
    if isinstance(frame, dict):
        frame = pd.concat(frame.values(), ignore_index=True)

    columns_by_norm = {normalize_header(column): column for column in frame.columns}
    loaded_players = 0
    loaded_measurements = 0
    loaded_boards = 0

    for _, row in frame.iterrows():
        raw_name = get_value(row, columns_by_norm, "name")
        if raw_name is None:
            continue

        name = str(raw_name).strip()
        player = resolve_player(session, name)
        update_player_profile(
            player,
            name=name,
            position=clean_cell(get_value(row, columns_by_norm, "position")),
            country=clean_cell(get_value(row, columns_by_norm, "country")),
            school=clean_cell(get_value(row, columns_by_norm, "school")),
        )
        loaded_players += 1

        row_payload = {
            normalize_header(column): clean_cell(row[column])
            for column in frame.columns
            if clean_cell(row[column]) is not None
        }
        source_hash = _stable_hash(
            {
                "source": source,
                "snapshot_date": snapshot_date.isoformat(),
                "row": row_payload,
            }
        )

        measurement_values = {
            "height_in": parse_inches(get_value(row, columns_by_norm, "height_in"), height_like=True),
            "wingspan_in": parse_inches(get_value(row, columns_by_norm, "wingspan_in"), height_like=True),
            "weight_lbs": parse_float(get_value(row, columns_by_norm, "weight_lbs")),
            "vertical_max_in": parse_inches(get_value(row, columns_by_norm, "vertical_max_in"), height_like=False),
            "sprint_sec": parse_float(get_value(row, columns_by_norm, "sprint_sec")),
            "hand_length_in": parse_inches(get_value(row, columns_by_norm, "hand_length_in"), height_like=False),
            "hand_width_in": parse_inches(get_value(row, columns_by_norm, "hand_width_in"), height_like=False),
        }
        if any(value is not None for value in measurement_values.values()):
            session.add(
                CombineMeasurement(
                    player_id=player.id,
                    source=source,
                    source_hash=source_hash,
                    snapshot_date=snapshot_date,
                    **measurement_values,
                )
            )
            loaded_measurements += 1

        pick_number = parse_int(get_value(row, columns_by_norm, "pick_number"))
        if pick_number is not None:
            row_board_type = clean_cell(get_value(row, columns_by_norm, "board_type"))
            session.add(
                DraftBoard(
                    player_id=player.id,
                    pick_number=pick_number,
                    board_type=normalize_mode(str(row_board_type or mode)),
                    source=source,
                    source_hash=source_hash,
                    snapshot_date=snapshot_date,
                )
            )
            loaded_boards += 1

    session.flush()
    return {
        "players_seen": loaded_players,
        "measurements_inserted": loaded_measurements,
        "board_entries_inserted": loaded_boards,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load NBA draft Excel data into the milestone DB.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--snapshot-date", required=True, type=date.fromisoformat)
    parser.add_argument("--source", default="excel-import")
    parser.add_argument("--board-type", default="projected", choices=["actual", "projected"])
    parser.add_argument("--sheet-name", default=0)
    parser.add_argument("--all-sheets", action="store_true")
    parser.add_argument("--create-schema", action="store_true")
    args = parser.parse_args()

    if args.create_schema:
        create_schema()

    sheet_name: str | int | None = None if args.all_sheets else args.sheet_name
    with SessionLocal() as session:
        stats = load_excel(
            session,
            args.path,
            snapshot_date=args.snapshot_date,
            source=args.source,
            board_type=args.board_type,
            sheet_name=sheet_name,
        )
        session.commit()
    print(stats)


if __name__ == "__main__":
    main()
