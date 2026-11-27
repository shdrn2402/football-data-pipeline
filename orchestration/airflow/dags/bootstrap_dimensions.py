from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG, Param

SHARED_DOCKER_ENV = {
    "AWS_ACCESS_KEY_ID": "{{ conn.aws_s3_conn.login }}",
    "AWS_SECRET_ACCESS_KEY": "{{ conn.aws_s3_conn.password }}",
    "AWS_DEFAULT_REGION": "{{ conn.aws_s3_conn.extra_dejson.get('region_name', 'eu-central-1') }}",
    "AWS_S3_LANDING_BUCKET_NAME": "{{ var.value.landing_bucket_name }}",
    "API_FOOTBALL_KEY": "{{ conn.api_football_conn.password }}",
    "API_DELAY_SECONDS": "{{ var.value.get('api_delay_seconds', '') }}",
    "UV_NO_CACHE": "1",
}

# Covers failures outside the request retries, such as S3 or the Docker daemon.
DEFAULT_ARGS = {
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="football_bootstrap_dimensions",
    description="One-off/seasonal bootstrap flow for Dimension tables. Extracts league metadata and teams/venues into raw Data Lake storage.",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    default_args=DEFAULT_ARGS,
    tags=["football", "dimension", "bootstrap"],
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
    run_ingest_league_dimension = DockerOperator(
        task_id="run_ingest_league_dimension",
        image="football-pipeline:latest",
        api_version="auto",
        auto_remove="force",
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        environment=SHARED_DOCKER_ENV,
        command="/app/.venv/bin/football-pipeline --endpoint leagues --league-id {{ params.league_id }}",
    )

    ingest_teams_dimension = DockerOperator(
        task_id="ingest_teams_dimension",
        image="football-pipeline:latest",
        api_version="auto",
        auto_remove="force",
        docker_url="unix://var/run/docker.sock",
        network_mode="bridge",
        environment=SHARED_DOCKER_ENV,
        command="/app/.venv/bin/football-pipeline --endpoint teams --league-id {{ params.league_id }} --season {{ params.season }}",
    )

    run_ingest_league_dimension >> ingest_teams_dimension
