import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

SQL_DIR = Path(__file__).parent / "sql"
REQUEST_TIMEOUT_SECONDS = (10, 300)


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


def build_fixtures_s3_url(league_id: int, season: int, target_date: str) -> str:
    """Builds the URL of one fixtures snapshot written by the ingestion step."""
    bucket = os.environ["AWS_S3_LANDING_BUCKET_NAME"]
    region = os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
    return (
        f"https://{bucket}.s3.{region}.amazonaws.com/raw/facts/fixtures/"
        f"league_id={league_id}/season={season}/date={target_date}/data.json"
    )


def escape_sql_string(value: str) -> str:
    """Escapes a value for use inside a single-quoted SQL literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def load_raw_snapshot(params: dict) -> None:
    """Copies one snapshot from S3 into the raw table.

    AWS keys go into the request body as literals rather than query parameters:
    ClickHouse masks them in its logs, and a URL could surface in network errors.
    """
    statement = (
        read_statements("load_raw_fixtures.sql")[0]
        .replace(
            "__AWS_ACCESS_KEY_ID__", escape_sql_string(os.environ["AWS_ACCESS_KEY_ID"])
        )
        .replace(
            "__AWS_SECRET_ACCESS_KEY__",
            escape_sql_string(os.environ["AWS_SECRET_ACCESS_KEY"]),
        )
    )
    execute(statement, params)
    logger.info("Loaded the S3 snapshot into raw_fixtures.")


def load_fixtures(league_id: int, season: int, target_date: str) -> None:
    """Loads one fixtures snapshot from S3 into the raw and staging tables.

    Raises:
        ValueError: If the snapshot holds no fixtures, to fail instead of staying green.
    """
    params = {
        "league_id": league_id,
        "season": season,
        "target_date": target_date,
        "s3_url": build_fixtures_s3_url(league_id, season, target_date),
    }
    run_sql_file("create_tables.sql")
    load_raw_snapshot(params)

    loaded = int(
        execute(
            "SELECT count() FROM raw_fixtures FINAL "
            "WHERE league_id = {league_id:UInt32} AND season = {season:UInt16} "
            "AND snapshot_date = {target_date:Date}",
            {"league_id": league_id, "season": season, "target_date": target_date},
        )
    )
    if loaded == 0:
        raise ValueError(
            f"No fixtures found in snapshot {params['s3_url']}. Check the extract step."
        )
    logger.info(f"Raw snapshot holds {loaded} fixtures.")

    run_sql_file("load_stg_fixtures.sql", params)


def build_team_points(league_id: int, season: int) -> None:
    """Rebuilds the team points mart for one league and season."""
    run_sql_file("create_tables.sql")
    run_sql_file(
        "build_mart_team_points.sql", {"league_id": league_id, "season": season}
    )
