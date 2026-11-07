from __future__ import annotations

from datetime import UTC, datetime

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG, Param

SHARED_DOCKER_ENV = {
    "AWS_ACCESS_KEY_ID": "{{ conn.aws_s3_conn.login }}",
    "AWS_SECRET_ACCESS_KEY": "{{ conn.aws_s3_conn.password }}",
    "AWS_DEFAULT_REGION": "{{ conn.aws_s3_conn.extra_dejson.get('region_name', 'eu-central-1') }}",
    "AWS_S3_LANDING_BUCKET_NAME": "{{ var.value.landing_bucket_name }}",
    "API_FOOTBALL_KEY": "{{ conn.api_football_conn.password }}",
    "UV_NO_CACHE": "1",
}

CLICKHOUSE_DOCKER_ENV = {
    "AWS_ACCESS_KEY_ID": "{{ conn.aws_s3_conn.login }}",
    "AWS_SECRET_ACCESS_KEY": "{{ conn.aws_s3_conn.password }}",
    "AWS_S3_LANDING_BUCKET_NAME": "{{ var.value.landing_bucket_name }}",
    "AWS_DEFAULT_REGION": "{{ conn.aws_s3_conn.extra_dejson.get('region_name', 'eu-central-1') }}",
    "CLICKHOUSE_HOST": "{{ conn.clickhouse_conn.host }}",
    "CLICKHOUSE_PORT": "{{ conn.clickhouse_conn.port }}",
    "CLICKHOUSE_USER": "{{ conn.clickhouse_conn.login }}",
    "CLICKHOUSE_PASSWORD": "{{ conn.clickhouse_conn.password }}",
    "CLICKHOUSE_DB": "{{ conn.clickhouse_conn.schema }}",
}

# Both the extract and load tasks must address the same S3 snapshot.
TARGET_DATE = "{{ dag_run.run_after.strftime('%Y-%m-%d') }}"

with DAG(
    dag_id="football_fixtures_elt",
    description="Extracts match results of a league season to S3, loads them into ClickHouse and builds the team points mart.",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    tags=["football", "fact", "fixtures"],
    params={
        "league_id": Param(
            default=39,
            type="integer",
            description="API-Football league ID (e.g., 39 for Premier League)",
        ),
        "season": Param(
            default=2023,
            type="integer",
            description="Target season year",
        ),
    },
) as dag:
    extract_fixtures = DockerOperator(
        task_id="extract_fixtures",
        image="football-pipeline:latest",
        api_version="auto",
        auto_remove="force",
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        environment=SHARED_DOCKER_ENV,
        command="/app/.venv/bin/football-pipeline --endpoint fixtures --league-id {{ params.league_id }} --season {{ params.season }} "
        f"--target-date {TARGET_DATE}",
    )

    load_fixtures_to_clickhouse = DockerOperator(
        task_id="load_fixtures_to_clickhouse",
        image="football-pipeline:latest",
        api_version="auto",
        auto_remove="force",
        docker_url="unix://var/run/docker.sock",
        network_mode="football_airflow",
        environment=CLICKHOUSE_DOCKER_ENV,
        command="/app/.venv/bin/football-warehouse load-fixtures --league-id {{ params.league_id }} --season {{ params.season }} "
        f"--target-date {TARGET_DATE}",
    )

    build_team_points_mart = DockerOperator(
        task_id="build_team_points_mart",
        image="football-pipeline:latest",
        api_version="auto",
        auto_remove="force",
        docker_url="unix://var/run/docker.sock",
        network_mode="football_airflow",
        environment=CLICKHOUSE_DOCKER_ENV,
        command="/app/.venv/bin/football-warehouse build-team-points --league-id {{ params.league_id }} --season {{ params.season }}",
    )

    extract_fixtures >> load_fixtures_to_clickhouse >> build_team_points_mart
