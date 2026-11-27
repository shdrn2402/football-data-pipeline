import logging
import os
from pathlib import Path

import requests

from football_pipeline.core.config import read_config
from football_pipeline.storage.s3 import (
    add_filter_partitions,
    build_s3_key,
    list_s3_objects,
)

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"
REQUEST_TIMEOUT_SECONDS = (10, 300)
# Match objects read by one INSERT.
MATCHES_PER_INSERT = 100
# Dataset name to the endpoint that wrote it. Injuries may be empty for a league.
SNAPSHOT_DATASETS = {
    "players": "players_statistics",
    "sidelined": "sidelined",
    "injuries": "injuries",
}
# Selects the raw rows of one snapshot.
SNAPSHOT_FILTER = (
    "league_id = {league_id:UInt32} AND season = {season:UInt16} "
    "AND snapshot_date = {snapshot_date:Date}"
)


def read_statements(file_name: str) -> list[str]:
    """Splits a SQL file into statements, as the HTTP interface accepts one per request."""
    sql = (SQL_DIR / file_name).read_text()
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def execute(statement: str, params: dict | None = None) -> str:
    """Runs one statement over the ClickHouse HTTP interface and returns the response body.

    Raises:
        RuntimeError: If ClickHouse rejects the statement.
        KeyError: If a required environment variable is missing.
    """
    host = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port = os.environ.get("CLICKHOUSE_PORT", "8123")
    query_params = {f"param_{key}": value for key, value in (params or {}).items()}
    query_params["database"] = os.environ["CLICKHOUSE_DB"]

    response = requests.post(
        f"http://{host}:{port}/",
        params=query_params,
        data=statement.encode(),
        headers={
            "X-ClickHouse-User": os.environ["CLICKHOUSE_USER"],
            "X-ClickHouse-Key": os.environ["CLICKHOUSE_PASSWORD"],
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(f"ClickHouse error {response.status_code}: {response.text}")
    return response.text.strip()


def run_sql_file(file_name: str, params: dict | None = None) -> None:
    """Executes every statement of a packaged SQL file, passing only the params it uses."""
    for statement in read_statements(file_name):
        used_params = {
            key: value
            for key, value in (params or {}).items()
            if f"{{{key}:" in statement
        }
        execute(statement, used_params)
    logger.info(f"Executed {file_name}.")


def build_s3_url(s3_key: str) -> str:
    """Builds the URL of an object of the landing bucket."""
    bucket = os.environ["AWS_S3_LANDING_BUCKET_NAME"]
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"


def build_snapshot_url(endpoint: str, filters: dict, snapshot_date: str) -> str:
    """Builds the URL of one snapshot written by the ingestion step.

    The object key comes from the same s3_template that ingestion writes with.
    """
    template = read_config()["api"]["endpoints"][endpoint]["s3_template"]
    s3_key = build_s3_key(
        add_filter_partitions(template, filters),
        snapshot_date=snapshot_date,
        **filters,
    )
    return build_s3_url(s3_key)


def build_fixtures_s3_url(league_id: int, season: int, snapshot_date: str) -> str:
    """Builds the URL of one fixtures snapshot."""
    filters = {"league": league_id, "season": season}
    return build_snapshot_url("fixtures", filters, snapshot_date)


def escape_sql_string(value: str) -> str:
    """Escapes a value for use inside a single-quoted SQL literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def load_raw_snapshot(params: dict, sql_file: str = "load_raw_fixtures.sql") -> None:
    """Copies S3 objects into a raw table.

    AWS keys go into the request body as literals rather than query parameters:
    ClickHouse masks them in its logs, and a URL could surface in network errors.
    """
    statement = (
        read_statements(sql_file)[0]
        .replace(
            "__AWS_ACCESS_KEY_ID__", escape_sql_string(os.environ["AWS_ACCESS_KEY_ID"])
        )
        .replace(
            "__AWS_SECRET_ACCESS_KEY__",
            escape_sql_string(os.environ["AWS_SECRET_ACCESS_KEY"]),
        )
    )
    execute(statement, params)
    logger.info(f"Executed {sql_file}.")


def load_fixtures(league_id: int, season: int, snapshot_date: str) -> None:
    """Loads one fixtures snapshot from S3 into the raw table.

    Raises:
        ValueError: If the snapshot holds no fixtures, to fail instead of staying
            green. The other quality checks are dbt tests.
    """
    snapshot = {
        "league_id": league_id,
        "season": season,
        "snapshot_date": snapshot_date,
    }
    params = {
        **snapshot,
        "s3_url": build_fixtures_s3_url(league_id, season, snapshot_date),
    }
    run_sql_file("create_tables.sql")
    # A row without a fixture ID is never replaced by a corrected one, so a row
    # left by a failed load would fail every later run of the same snapshot.
    execute(
        f"DELETE FROM raw_fixtures WHERE {SNAPSHOT_FILTER} AND fixture_id = 0",
        snapshot,
    )
    load_raw_snapshot(params)

    loaded = int(
        execute(
            f"SELECT count() FROM raw_fixtures FINAL WHERE {SNAPSHOT_FILTER}",
            snapshot,
        )
    )
    if loaded == 0:
        raise ValueError(
            f"No fixtures found in snapshot {params['s3_url']}. Check the extract step."
        )
    logger.info(f"Raw snapshot holds {loaded} fixtures.")


def find_changed_match_objects() -> list[int]:
    """Returns matches whose S3 object is new or changed since it was loaded."""
    template = read_config()["api"]["endpoints"]["match_details"]["s3_template"]
    objects = list_s3_objects(
        os.environ["AWS_S3_LANDING_BUCKET_NAME"], template.partition("{")[0]
    )
    rows = execute(
        "SELECT fixture_id, toUnixTimestamp(max(source_modified_at)) "
        "FROM raw_match_details GROUP BY fixture_id"
    )
    loaded = dict(tuple(map(int, row.split("\t"))) for row in rows.splitlines())

    changed = []
    for key, modified_at in objects.items():
        fixture_id = int(key.partition("fixture_id=")[2].partition("/")[0])
        if int(modified_at.timestamp()) > loaded.get(fixture_id, 0):
            changed.append(fixture_id)
    return sorted(changed)


def load_match_details() -> None:
    """Loads new and changed match details from S3 into the raw table."""
    run_sql_file("create_tables.sql")
    changed = find_changed_match_objects()
    template = read_config()["api"]["endpoints"]["match_details"]["s3_template"]
    for start in range(0, len(changed), MATCHES_PER_INSERT):
        batch = [str(item) for item in changed[start : start + MATCHES_PER_INSERT]]
        # A brace list makes ClickHouse read several objects at once.
        selector = batch[0] if len(batch) == 1 else "{" + ",".join(batch) + "}"
        s3_url = build_s3_url(build_s3_key(template, fixture=selector))
        load_raw_snapshot({"s3_url": s3_url}, "load_raw_match_details.sql")
    logger.info(f"Loaded {len(changed)} new or changed matches.")


def load_player_snapshot(
    dataset: str,
    league_id: int,
    season: int,
    snapshot_date: str,
    team_id: int | None = None,
) -> None:
    """Replaces one players, sidelined or injuries snapshot in its raw table.

    Raises:
        ValueError: If a players or sidelined snapshot loaded no rows.
    """
    filters = {"league": league_id, "season": season}
    if team_id is not None:
        filters["team"] = team_id
    s3_url = build_snapshot_url(SNAPSHOT_DATASETS[dataset], filters, snapshot_date)
    snapshot = {
        "league_id": league_id,
        "season": season,
        "snapshot_date": snapshot_date,
    }
    run_sql_file("create_tables.sql")
    # A team snapshot holds a part of the league, so only a league load replaces all.
    if team_id is None:
        execute(f"DELETE FROM raw_{dataset} WHERE {SNAPSHOT_FILTER}", snapshot)
    load_raw_snapshot({**snapshot, "s3_url": s3_url}, f"load_raw_{dataset}.sql")

    loaded = int(
        execute(
            f"SELECT count() FROM raw_{dataset} FINAL WHERE {SNAPSHOT_FILTER}",
            snapshot,
        )
    )
    if loaded == 0 and dataset != "injuries":
        raise ValueError(f"No rows found in snapshot {s3_url}. Check the extract step.")
    logger.info(f"raw_{dataset} holds {loaded} rows of the snapshot.")


def build_team_points(league_id: int, season: int) -> None:
    """Rebuilds the team points mart for one league and season."""
    run_sql_file("create_tables.sql")
    run_sql_file(
        "build_mart_team_points.sql", {"league_id": league_id, "season": season}
    )
