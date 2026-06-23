from datetime import date
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.milestones import compute_milestones
from app.models import Base, CombineMeasurement, DraftBoard, Player


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_player(
    session,
    *,
    name,
    position,
    country,
    school,
    pick,
    height,
    wingspan,
    vertical,
    hand_length,
):
    player = Player(
        id=uuid.uuid4(),
        name=name,
        name_norm=name.lower().replace(" ", ""),
        position=position,
        position_bucket="C" if position == "C" else position,
        country=country,
        is_international=country != "USA",
        school=school,
    )
    session.add(player)
    session.flush()
    session.add(
        CombineMeasurement(
            id=uuid.uuid4(),
            player_id=player.id,
            height_in=height,
            wingspan_in=wingspan,
            weight_lbs=220,
            vertical_max_in=vertical,
            sprint_sec=3.2,
            hand_length_in=hand_length,
            hand_width_in=9.0,
            source="test",
            source_hash=name,
            snapshot_date=date(2026, 6, 1),
        )
    )
    session.add(
        DraftBoard(
            id=uuid.uuid4(),
            player_id=player.id,
            pick_number=pick,
            board_type="projected",
            snapshot_date=date(2026, 6, 1),
            source="test",
            source_hash=name,
        )
    )
    return player


def test_compute_all_milestones_from_snapshots():
    session = make_session()
    add_player(
        session,
        name="Wing A",
        position="F",
        country="USA",
        school="Duke",
        pick=4,
        height=80,
        wingspan=86,
        vertical=40,
        hand_length=9.5,
    )
    add_player(
        session,
        name="Guard B",
        position="G",
        country="USA",
        school="Duke",
        pick=2,
        height=76,
        wingspan=79,
        vertical=44,
        hand_length=8.5,
    )
    add_player(
        session,
        name="Center C",
        position="C",
        country="USA",
        school="UConn",
        pick=10,
        height=84,
        wingspan=90,
        vertical=30,
        hand_length=10.0,
    )
    add_player(
        session,
        name="Intl D",
        position="F",
        country="France",
        school="Paris",
        pick=31,
        height=81,
        wingspan=87,
        vertical=42,
        hand_length=10.2,
    )
    add_player(
        session,
        name="Intl E",
        position="G",
        country="Spain",
        school="Real Madrid",
        pick=20,
        height=78,
        wingspan=80,
        vertical=35,
        hand_length=9.8,
    )
    session.commit()

    run, answers, snapshot = compute_milestones(session, date(2026, 6, 1), "projected")
    session.commit()

    answer_map = {answer.question_code: answer.answer for answer in answers}
    assert str(run.id)
    assert snapshot.player_count == 5
    assert snapshot.board_count == 5
    assert answer_map == {
        "Q1": 2,
        "Q2": 2,
        "Q3": 1,
        "Q4": 10,
        "Q5": 1,
        "Q6": "Duke",
        "Q7": 4,
    }

    _, answers_again, snapshot_again = compute_milestones(session, date(2026, 6, 1), "projected")
    assert [answer.answer for answer in answers_again] == [answer.answer for answer in answers]
    assert snapshot_again.source_hash == snapshot.source_hash
