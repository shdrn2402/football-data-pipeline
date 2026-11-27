"""Runs the player staging models against a real ClickHouse."""

import json

import pytest

from football_pipeline.warehouse import clickhouse
from football_pipeline.warehouse.transform import build_player_staging


def player(player_id, minutes=90, substitute=False, **statistics):
    games = {"minutes": minutes, "substitute": substitute, "rating": "7.5"}
    return {
        "player": {"id": player_id, "name": f"Player {player_id}"},
        "statistics": [{"games": games, "cards": {"yellow": 0}, **statistics}],
    }


def insert_match(version, players, fixture_id=1, team_id=33):
    """Inserts one version of a match; a higher version is a later download."""
    payload = {
        "fixture": {
            "id": fixture_id,
            "date": "2023-08-11T19:00:00+00:00",
            "status": {"short": "FT"},
        },
        "teams": {"home": {"id": team_id}, "away": {"id": 50}},
        "goals": {"home": 2, "away": 1},
        "players": [{"team": {"id": team_id, "name": "Home"}, "players": players}],
    }
    clickhouse.execute(
        "INSERT INTO raw_match_details VALUES (88, 2023, {id:UInt64}, "
        "toDateTime64({version:UInt32}, 3, 'UTC'), {version:UInt32}, "
        "{payload:String})",
        {"id": fixture_id, "version": version, "payload": json.dumps(payload)},
    )


def query(sql):
    return clickhouse.execute(sql).splitlines()


def staged_players():
    return query("SELECT player_id FROM stg_player_matches ORDER BY player_id")


def test_a_reloaded_match_is_replaced_as_a_whole(database):
    passes = {"passes": {"total": 10, "accuracy": "8"}}
    insert_match(1, [player(1, **passes), player(2, **passes)])
    insert_match(1, [player(7, **passes)], fixture_id=2)
    build_player_staging()
    build_player_staging()
    assert staged_players() == ["1", "2", "7"]

    insert_match(2, [player(1, **passes), player(3, **passes)])
    build_player_staging()

    assert staged_players() == ["1", "3", "7"]


def test_statistics_keep_missing_data_apart_from_zero(database):
    insert_match(
        1,
        [
            player(1, passes={"total": 44, "accuracy": "31"}, goals={"total": 1}),
            player(2, passes={"total": None, "accuracy": None}),
            player(3, minutes=None, substitute=True),
        ],
    )
    # A match without any pass count has no player statistics.
    insert_match(1, [player(4)], fixture_id=2)

    build_player_staging()

    rows = query(
        "SELECT player_id, minutes_played, is_starter, rating, goals, "
        "passes_total, passes_accurate FROM stg_player_matches ORDER BY player_id"
    )
    assert rows == [
        "1\t90\t1\t7.5\t1\t44\t31",
        "2\t90\t1\t7.5\t0\t0\t0",
        "3\t0\t0\t7.5\t\\N\t\\N\t\\N",
        "4\t90\t1\t7.5\t\\N\t\\N\t\\N",
    ]


def test_a_broken_match_fails_without_changing_staging(database):
    insert_match(1, [player(1)])
    build_player_staging()
    insert_match(2, [player(2)], team_id=0)

    with pytest.raises(RuntimeError):
        build_player_staging()

    assert staged_players() == ["1"]


def insert_sidelined(day, player_id, periods):
    clickhouse.execute(
        "INSERT INTO raw_sidelined VALUES (88, 2023, {day:Date}, {id:UInt64}, "
        "toDateTime64({day:Date}, 3, 'UTC'), {periods:String})",
        {"day": day, "id": player_id, "periods": json.dumps(periods)},
    )


def insert_injury(day, player_id):
    payload = {
        "player": {"type": "Missing Fixture", "reason": "Knee Injury"},
        "team": {"id": 33},
        "fixture": {"date": "2023-08-11T19:00:00+00:00"},
    }
    clickhouse.execute(
        "INSERT INTO raw_injuries VALUES (88, 2023, {day:Date}, 1, {id:UInt64}, "
        "toDateTime64({day:Date}, 3, 'UTC'), {payload:String})",
        {"day": day, "id": player_id, "payload": json.dumps(payload)},
    )


def test_absences_follow_the_latest_answer(database):
    old = {"type": "Knock", "start": "2023-09-01", "end": "2023-09-05"}
    new = {"type": "Illness", "start": "1999-10-01", "end": None}
    insert_sidelined("2026-11-01", 1, [old])
    insert_sidelined("2026-11-01", 2, [])
    insert_sidelined("2026-11-02", 1, [new])
    insert_injury("2026-11-01", 1)
    insert_injury("2026-11-01", 2)
    insert_injury("2026-11-02", 1)

    build_player_staging()

    assert query("SELECT player_id FROM stg_sidelined_players ORDER BY 1") == ["1", "2"]
    assert query(
        "SELECT player_id, type, start_date, end_date FROM stg_sidelined_periods"
    ) == ["1\tIllness\t1999-10-01\t\\N"]
    # The injury row withdrawn by the later snapshot is gone.
    assert query("SELECT player_id FROM stg_injuries") == ["1"]


def test_the_latest_profile_wins(database):
    for day, nationality in (("2026-11-01", "Spain"), ("2026-11-02", "Ghana")):
        payload = {
            "player": {
                "id": 1,
                "birth": {"date": "1965-05-13"},
                "nationality": nationality,
            }
        }
        clickhouse.execute(
            "INSERT INTO raw_players VALUES (88, 2023, {day:Date}, 1, "
            "toDateTime64({day:Date}, 3, 'UTC'), {payload:String})",
            {"day": day, "payload": json.dumps(payload)},
        )

    build_player_staging()

    assert query("SELECT player_id, birth_date, nationality FROM stg_players") == [
        "1\t1965-05-13\tGhana"
    ]
