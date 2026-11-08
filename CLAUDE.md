# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Python 3.13, managed with `uv`. CI (`.github/workflows/ci.yaml`, runs on PRs to `main`) runs exactly these:

```bash
uv sync --frozen --dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest tests/
```

Single test: `uv run pytest tests/unit/test_warehouse.py::test_load_fixtures_fails_on_empty_snapshot`

Two console scripts (defined in `pyproject.toml`):

```bash
uv run football-pipeline --endpoint fixtures --league-id 39 --season 2023 --target-date 2026-11-08   # API -> S3
uv run football-warehouse load-fixtures --league-id 39 --season 2023 --target-date 2026-11-08        # S3 -> ClickHouse raw/stg
uv run football-warehouse build-team-points --league-id 39 --season 2023                             # stg -> mart
```

Orchestration stacks (run only one at a time; both bind ports 8080, 8123, 9000):

```bash
docker build -t football-pipeline:latest .   # required: DAGs/flows run this image, rebuild after code changes
docker compose --env-file .env -f orchestration/airflow/compose.yaml up -d
docker compose --env-file .env -f orchestration/kestra/compose.yaml up -d
```

## Architecture

ELT pipeline: API-Sports (API-Football v3) → S3 landing zone (raw JSON) → ClickHouse (raw → staging → mart). Infra in `terraform/` (S3 bucket, IAM) with remote state from `terraform-backend/`.

**Ingestion (`football-pipeline`)** — `cli.py` → `services/ingestion.py` → `extractors/football_api.py` (pagination, rate-limit sleep) → `domain/schemas.py` → `storage/s3.py`.
- Endpoints are data-driven by `configs/config.yaml`: each entry has `path`, `allowed_params` (whitelist of query params actually sent) and `s3_template` (S3 key layout). Adding an endpoint means adding a config entry and a `click.Choice` value in `cli.py`.
- `ingestion.py` builds a superset of args, then filters by `allowed_params`. E.g. `fixtures` does not allow `date`, so it always fetches the whole season.
- Every S3 object is a `DataEnvelope`: `{"_metadata": {ingested_at, source, endpoint, params, target_date}, "payload": <raw API response>}`, written to `<s3_template>/data.json`.
- `date=` in S3 paths is the **snapshot (extraction) date**, not the match date; all snapshots are kept.

**Warehouse (`football-warehouse`)** — `warehouse/clickhouse.py` talks to ClickHouse over the HTTP interface with plain `requests` (no driver).
- SQL lives in `warehouse/sql/*.sql`, split on `;` (one statement per HTTP request). Parameters use ClickHouse `{name:Type}` syntax and are sent as `param_<name>`; `run_sql_file` passes only params a statement references.
- `create_tables.sql` is idempotent and runs before each load/build.
- AWS keys for the `s3()` table function are substituted into SQL as escaped literals (`__AWS_ACCESS_KEY_ID__` placeholders), deliberately not as query params, so they're masked in ClickHouse logs.
- `build_fixtures_s3_url` must stay in sync with the `fixtures` `s3_template` (covered by a test).
- `load_fixtures` raises if the snapshot loaded 0 rows, so an empty extract fails the DAG instead of staying green.
- Data model: `raw_fixtures` and `stg_fixtures` are `ReplacingMergeTree(ingested_at)` partitioned by `(league_id, season)` — always read them with `FINAL`. `ORDER BY` is the dedup key (raw: per snapshot; stg: per match). Don't partition by match date (rescheduled matches would duplicate across partitions). `mart_team_points` is a plain `MergeTree` rebuilt per league/season. See README "ClickHouse Data Model" for rationale.

**Orchestration** — Airflow (`orchestration/airflow/dags/`) and Kestra (`orchestration/kestra/flows/`) are alternative stacks; both only launch the `football-pipeline:latest` container (Airflow via `DockerOperator` over the mounted docker socket). No business logic lives in DAGs.
- `football_fixtures_elt` (Airflow only, `schedule=None`): extract → load → mart. Extract and load must share `TARGET_DATE` (`dag_run.run_after`) to address the same snapshot.
- Warehouse tasks join the fixed Docker network `football_airflow` to reach the `clickhouse` service; the extract task uses `bridge`.
- `football_bootstrap_dimensions` exists in both Airflow and Kestra (leagues, teams).

**Configuration / env vars** — the code reads unprefixed names (`API_FOOTBALL_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_LANDING_BUCKET_NAME`, `CLICKHOUSE_HOST/PORT/USER/PASSWORD/DB`). The root `.env` (template: `env.example`) uses `FLOW_`-prefixed secrets, which the orchestrators map: Airflow compose turns them into connections `aws_s3_conn`, `api_football_conn`, `clickhouse_conn` and variable `landing_bucket_name`; Kestra exposes them via `env-vars-prefix: "FLOW_"` as `envs.*`. `PIPELINE_CONFIG_PATH` / `PIPELINE_ENV_PATH` override config/.env locations.

**Tests** — unit tests only (`tests/unit/`), no external services: network, S3 and ClickHouse calls are replaced with `monkeypatch.setattr` on module-level functions (e.g. `ingestion.fetch_data`, `clickhouse.execute`). Keep functions module-level so this pattern keeps working.

## Conventions

Commit, issue, PR and branch conventions (must follow):

@CONTRIBUTING.md
