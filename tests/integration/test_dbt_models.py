"""Runs the dbt models against a real ClickHouse, in a temporary database.

Skipped unless RUN_INTEGRATION_TESTS=1 and the CLICKHOUSE_* variables are set.
"""

import json
import os

import pytest

from football_pipeline.warehouse import clickhouse
from football_pipeline.warehouse.transform import build_staging

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="needs a running ClickHouse",
)

DATABASE = "dbt_integration_test"


@pytest.fixture
def database(monkeypatch):
    clickhouse.execute(f"DROP DATABASE IF EXISTS {DATABASE}")
    clickhouse.execute(f"CREATE DATABASE {DATABASE}")
    monkeypatch.setenv("CLICKHOUSE_DB", DATABASE)
    clickhouse.run_sql_file("create_tables.sql")
    yield
    clickhouse.execute(f"DROP DATABASE {DATABASE}")


def insert_raw(snapshot_date, fixture_id, home_goals=2, home_team_id=33):
    payload = {
        "fixture": {
            "id": fixture_id,
            "date": "2023-08-11T19:00:00+00:00",
            "status": {"short": "FT"},
        },
        "league": {"round": "Regular Season - 1"},
        "teams": {
            "home": {"id": home_team_id, "name": "Home"},
            "away": {"id": 50, "name": "Away"},
        },
        "goals": {"home": home_goals, "away": None},
    }
    clickhouse.execute(
        "INSERT INTO raw_fixtures VALUES (39, 2023, {day:Date}, {id:UInt64}, "
        "toDateTime64({day:Date}, 3, 'UTC'), {payload:String})",
        {"day": snapshot_date, "id": fixture_id, "payload": json.dumps(payload)},
    )


def staging():
    return clickhouse.execute(
        "SELECT fixture_id, status, home_team_id, home_goals, away_goals "
        "FROM stg_fixtures FINAL ORDER BY fixture_id"
    )


def test_a_newer_snapshot_replaces_matches_and_keeps_one_row_each(database):
    insert_raw("2026-11-01", 1, home_goals=1)
    insert_raw("2026-11-01", 2)
    build_staging(39, 2023, "2026-11-01")
    insert_raw("2026-11-02", 1, home_goals=3)

    build_staging(39, 2023, "2026-11-02")

    assert staging().splitlines() == ["1\tFT\t33\t3\t\\N", "2\tFT\t33\t2\t\\N"]


@pytest.mark.parametrize(("fixture_id", "home_team_id"), [(0, 33), (3, 0)])
def test_a_broken_snapshot_fails_without_changing_staging(
    database, fixture_id, home_team_id
):
    insert_raw("2026-11-01", 1)
    build_staging(39, 2023, "2026-11-01")
    before = staging()
    insert_raw("2026-11-02", 1, home_goals=9)
    insert_raw("2026-11-02", fixture_id, home_team_id=home_team_id)

    with pytest.raises(RuntimeError):
        build_staging(39, 2023, "2026-11-02")

    assert staging() == before
