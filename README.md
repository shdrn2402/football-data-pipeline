# ⚽ Football Data Pipeline (ELT)

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![Package Manager: uv](https://img.shields.io/badge/package--manager-uv-brightgreen)](https://docs.astral.sh/uv/)
[![IaC: Terraform](https://img.shields.io/badge/IaC-Terraform-purple)](https://www.terraform.io/)
[![Cloud: AWS S3](https://img.shields.io/badge/Cloud-AWS%20S3-orange)](https://aws.amazon.com/s3/)
[![Orchestrator: Airflow & Kestra](https://img.shields.io/badge/Orchestrator-Airflow%20%7C%20Kestra-blueviolet)]()
[![Project Status: In Progress](https://img.shields.io/badge/Status-In%20Progress-yellow)](#)

An end-to-end Data Engineering ELT pipeline designed to extract football sports statistics from API-Sports, store raw JSON payloads into an AWS S3 Data Lake, and automate batch execution workflows with Apache Airflow or Kestra.

>💡 Project Background:
>This project is inspired by the DataTalks.Club Data Engineering Zoomcamp, but completely re-engineered around a live external sports domain instead of the default NYC Taxi dataset.
>It features a custom CLI-based ingestion tool with pagination and API rate-limiting, optimized container packaging using Astral uv for fast dependency management executed under an unprivileged user, and fully automated cloud infrastructure provisioned via Terraform with remote S3 state storage and native S3 state locking.

## 🏗 System Architecture

```mermaid
flowchart TD
    subgraph Infrastructure ["Infrastructure as Code (Terraform)"]
        TF[Terraform] -.->|Provisions & Manages| S3[(AWS S3 Data Lake)]
        TF -.->|Scoped Policies| IAM[AWS IAM Data Loader]
    end

    subgraph Orchestration ["Orchestration Layer"]
        Airflow[Apache Airflow] -->|Triggers Manual Job| IngestApp[Containerized Python CLI]
        Kestra[Kestra Orchestrator] -->|Triggers Manual Job| IngestApp
    end

    subgraph DataFlow ["Data Ingestion Flow"]
        API[API-Sports REST API] -->|Paginated Requests & Rate Limits| IngestApp
        IngestApp -->|Boto3 / Raw JSON| S3
    end

    subgraph Warehouse ["Data Warehouse (Airflow)"]
        S3 -->|s3 table function| Raw[(ClickHouse raw)]
        Raw -->|dbt model and tests| Staging[(ClickHouse staging)]
        Staging -->|SQL| Mart[(Team points mart)]
    end

    subgraph FutureScope ["Planned Analytics"]
        Staging -.->|dbt model| Scouting[Scouting mart]
        Scouting -.-> BI[Dashboards]
    end
```

---

## ⚙️ Key Technical Features

* **Infrastructure as Code (IaC):** AWS S3 landing bucket and scoped IAM ingestion policies managed via **Terraform** (AWS provider ~> 6.0) with remote state in S3 and native S3 state locking. Both buckets are versioned and cannot be destroyed while they hold objects.
* **Resilient Ingestion Engine (`src/`):** Parameterized CLI built with `click` and `requests`. Features automated pagination, rate-limit sleep windows, dynamic S3 folder partitioning from per-endpoint templates (e.g. `league_id / season / date`), and structured logging.
* **Orchestration Layer:** **Apache Airflow 3.3.2** and **Kestra 2.0** available as alternative Docker Compose stacks, each backed by its own PostgreSQL 18 metadata database for task execution.
* **Local Data Warehouse:** **ClickHouse 26.8 LTS** included in each orchestration stack, with persistent volumes and a health check. The Airflow DAG `football_fixtures_elt` loads match results from S3 into a raw table, builds staging with **dbt** and builds a team points mart.
* **Secure & Fast Containerization:** Lightweight Docker images leveraging Astral `uv` for sub-second dependency resolution, running under an unprivileged user (`ingest_user`) for container security.

---

## 📂 Repository Structure

```text
football-data-pipeline/
├── configs/                  # Pipeline configs and API endpoint definitions
├── orchestration/            
│   ├── airflow/              # Apache Airflow compose.yaml and DAGs
│   └── kestra/               # Kestra compose.yaml and Flows
├── src/                      # Clean Architecture source code
│   └── football_pipeline/
│       ├── cli.py            # CLI entrypoint
│       ├── core/             # Configuration and logging
│       ├── domain/           # Domain schemas and entities
│       ├── extractors/       # API-Sports extraction clients
│       ├── services/         # Ingestion orchestration services
│       ├── storage/          # S3 storage clients and uploaders
│       └── warehouse/        # ClickHouse loading CLI, SQL and the dbt project
├── terraform/                # IaC definitions (S3, IAM)
├── terraform-backend/        # IaC state bucket definition
├── tests/                    # Unit test suite
├── Dockerfile                # Hardened container build recipe (Python 3.13 + uv)
├── pyproject.toml            # Project packaging metadata and build definitions
└── uv.lock                   # Locked dependency tree
```

## 🛠 Tech Stack

| Domain | Tools / Technologies |
| :--- | :--- |
| **Language** | Python 3.13 |
| **Dependency Management** | Astral `uv`, `hatchling` |
| **CLI Framework** | `click` |
| **Cloud Storage** | AWS S3 |
| **Infrastructure as Code** | Terraform (AWS Provider ~> 6.0) |
| **Orchestration** | Apache Airflow 3.3.2, Kestra 2.0, PostgreSQL 18 |
| **Data Warehouse** | ClickHouse 26.8 LTS |
| **Transformations** | dbt Core 1.12 with `dbt-clickhouse` |
| **Containerization** | Docker, Docker Compose |

---

## 🚀 Setup & Quickstart

### 1. Provision Infrastructure with Terraform
Navigate to the terraform directory to initialize and deploy the S3 Data Lake and IAM credentials:
```bash
# 1. Create the remote state bucket
cd terraform-backend
terraform init
terraform apply -auto-approve

# 2. Provision landing zone and IAM
cd ../terraform
terraform init
terraform plan -var="environment=dev"
terraform apply -var="environment=dev"
```

#### Restoring an overwritten object
The landing bucket keeps replaced and deleted versions for 90 days (`noncurrent_version_retention_days`). Restoring needs credentials that may read versions, which the data loader user does not have:
```bash
aws s3api list-object-versions --bucket <bucket> --prefix <key>
aws s3api copy-object --bucket <bucket> --key <key> --copy-source "<bucket>/<key>?versionId=<version-id>"
```

### 2. Configure Environment Variables
Create a .env file in the project root based on your credentials:

```.env
# Ingestion API Configuration
FLOW_API_FOOTBALL_KEY=your_football_api_key

# AWS Configuration & Credentials
FLOW_AWS_ACCESS_KEY_ID=your_aws_access_key_id
FLOW_AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_DEFAULT_REGION=eu-central-1
AWS_S3_LANDING_BUCKET_NAME=football-data-pipeline-landing-zone-dev

# Airflow Credentials & Security
AIRFLOW_POSTGRES_USER=airflow
AIRFLOW_POSTGRES_PASSWORD=airflow
AIRFLOW_POSTGRES_DB=airflow
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=admin
AIRFLOW_UID=50000
AIRFLOW_DOCKER_GID=999
FERNET_KEY=your_fernet_key_here
AIRFLOW__API_AUTH__JWT_SECRET=your_generated_jwt_secret_here
AIRFLOW__API_AUTH__JWT_ISSUER=football-data-pipeline

# Kestra Credentials
KESTRA_POSTGRES_USER=kestra
KESTRA_POSTGRES_PASSWORD=kestra_password
KESTRA_POSTGRES_DB=kestra
KESTRA_USER=admin@example.com
KESTRA_PASSWORD=admin_password

# ClickHouse Credentials
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=your_clickhouse_db_password
CLICKHOUSE_DB=clickhouse
```

### 3. Build the Ingestion Image
The manual Docker run, Airflow DAG, and Kestra flow all use this image:
```bash
docker build -t football-pipeline:latest .
```

### 4. Launch Orchestrator
Launch Airflow:
```bash
docker compose --env-file .env -f orchestration/airflow/compose.yaml up -d
```

Or Kestra:
```bash
docker compose --env-file .env -f orchestration/kestra/compose.yaml up -d
```

Run one stack at a time: both publish ports `8080`, `8123`, and `9000`. Each stack has its own ClickHouse instance and volumes, so data is not shared between them.

| Service | Address |
| :--- | :--- |
| Airflow or Kestra Web UI | `http://localhost:8080` |
| ClickHouse health check | `http://localhost:8123/ping` |
| ClickHouse SQL UI | `http://localhost:8123/play` |
| ClickHouse native TCP | `localhost:9000` |

### 5. Run the CLIs Manually
The root `.env` holds `FLOW_`-prefixed secrets for the orchestrators, while the code reads unprefixed names. For local runs, create a separate file from the template and fill it in:
```bash
cp env.local.example .env.local
```

Both CLIs load the file named by `PIPELINE_ENV_PATH` (default: `.env`). Variables already set in the environment take precedence.
```bash
export PIPELINE_ENV_PATH=.env.local

uv run football-pipeline --endpoint leagues --league-id 39
uv run football-pipeline --endpoint fixtures --league-id 39 --season 2023 --snapshot-date 2026-11-08

# Requires the ClickHouse service of a running stack (step 4)
uv run football-warehouse load-fixtures --league-id 39 --season 2023 --snapshot-date 2026-11-08
uv run football-warehouse build-staging --league-id 39 --season 2023 --snapshot-date 2026-11-08
uv run football-warehouse build-team-points --league-id 39 --season 2023
```

Match details (events, lineups, team and player statistics) are downloaded for the finished matches of a fixtures snapshot, so extract the snapshot first:
```bash
uv run football-pipeline --endpoint match_details --league-id 39 --season 2023 --snapshot-date 2026-11-08 --max-fixtures 3
```
Each match is stored as `raw/facts/match_details/fixture_id=<id>/data.json`. Stored matches are skipped, so repeated runs continue the season. `--fixture-id` downloads one match again. `batch_size` in `configs/config.yaml` switches between one match per request (free plan) and up to 20 (paid plan).

Player profiles (date of birth, nationality) come with `players_statistics`. `sidelined` then downloads the injury and suspension periods of those players, 20 per request. The free plan returns only 3 pages of players, so try it on one team:
```bash
uv run football-pipeline --endpoint players_statistics --league-id 88 --season 2023 --team-id 194
uv run football-pipeline --endpoint sidelined --league-id 88 --season 2023 --team-id 194
```
Both commands must use the same `--snapshot-date` (default: today).

Or run the ingestion inside the Docker container:
```bash
docker run --rm --env-file .env.local football-pipeline:latest football-pipeline --endpoint leagues --league-id 39
```

### 6. Run the Fixtures ELT DAG
Unpause and trigger `football_fixtures_elt` in the Airflow UI (parameters: `league_id`, `season`). It runs four tasks:

1. `extract_fixtures`: API-Football to S3.
2. `load_fixtures_to_clickhouse`: S3 to `raw_fixtures`.
3. `build_staging_models`: dbt tests the raw snapshot, builds `stg_fixtures` and tests it.
4. `build_team_points_mart`: `stg_fixtures` to `mart_team_points`.

Check the result in the ClickHouse SQL UI. It connects to the `default` database, so qualify tables with your `CLICKHOUSE_DB` (`clickhouse` in `env.example`):
```sql
SELECT team_name, played, wins, draws, losses, points
FROM clickhouse.mart_team_points
WHERE league_id = 39 AND season = 2023
ORDER BY points DESC, goals_for - goals_against DESC;
```

![Team points mart for Premier League 2023](docs/screenshots/clickhouse_mart_team_points.png)

The DAG exists only in Airflow for now; Kestra still runs the dimensions bootstrap only.

---

## 🗄 ClickHouse Data Model

Each S3 path contains `date=<snapshot date>`, the day the data was extracted rather than the day a match was played. Every snapshot of a season stays in S3, and ClickHouse resolves them to one row per match.

| Table | ENGINE | PARTITION BY | ORDER BY |
| :--- | :--- | :--- | :--- |
| `raw_fixtures` | `ReplacingMergeTree(ingested_at)` | `(league_id, season)` | `(league_id, season, snapshot_date, fixture_id)` |
| `stg_fixtures` | `ReplacingMergeTree(ingested_at)` | `(league_id, season)` | `(league_id, season, fixture_id)` |
| `mart_team_points` | `MergeTree` | `(league_id, season)` | `(league_id, season, team_id)` |

**ENGINE.** Raw and staging use `ReplacingMergeTree` because loads repeat: rows with the same `ORDER BY` key are collapsed and the latest `ingested_at` wins, so a corrected score replaces the old one. The mart is rebuilt from scratch for its league and season, so it has nothing to deduplicate and a plain `MergeTree` is enough.

**ORDER BY.** In ClickHouse this is also the deduplication key, so it defines what one row means. In `raw_fixtures` that is a match in a given snapshot, which keeps history. In `stg_fixtures` it is a match, which keeps only the current state. Queries always filter by league and season, so those columns come first.

**PARTITION BY.** `ReplacingMergeTree` only deduplicates within a partition, so the partition key must not change for a given match. That rules out partitioning by match date: a rescheduled match would move to another partition and stay duplicated. League and season never change for a match, keep the partition count low, and let the mart drop exactly one season when it is rebuilt.

**Re-runs and duplicates.** Replacement happens during background merges, so duplicates can physically exist for a while. Read `raw_fixtures` and `stg_fixtures` with `FINAL`, as the pipeline does:

```sql
SELECT count() AS physical_rows, uniqExact(fixture_id) AS matches FROM clickhouse.stg_fixtures;  -- rows may exceed matches
SELECT count() FROM clickhouse.stg_fixtures FINAL;  -- always one row per match
```

After the DAG ran twice, `stg_fixtures` physically held 760 rows, and `FINAL` returned one row for each of the 380 matches:

![Deduplicated fixtures after a repeated DAG run](docs/screenshots/clickhouse_stg_fixtures_final.png)

**Transformations.** `raw_fixtures` is created and loaded by Python. Staging is built and owned by dbt (`src/football_pipeline/warehouse/dbt`): `stg_fixtures` is an incremental model that appends one snapshot per run. It ignores `--full-refresh`, as rebuilding it from one snapshot would drop all other seasons.

**Data quality checks.** The load fails if the snapshot is empty. `dbt build` runs two tests: the first checks the raw snapshot for zero fixture or team IDs (the response format changed) and, on failure, skips the model, so such rows never reach staging; the second checks that every fixture of the snapshot reached staging. CI runs the models and both outcomes against a real ClickHouse.

**Known limitation.** `mart_team_points` counts points from match results only. Points deductions are not in the fixtures data, so a sanctioned team shows more points than the official table.

### Player staging

Player data goes through the same raw and staging layers. Python loads S3 objects into raw tables, dbt builds and tests staging:
```bash
uv run football-warehouse load-match-details    # new and changed matches only
uv run football-warehouse load-player-snapshot --dataset players   --league-id 88 --season 2023 --snapshot-date 2026-11-08
uv run football-warehouse load-player-snapshot --dataset sidelined --league-id 88 --season 2023 --snapshot-date 2026-11-08
uv run football-warehouse load-player-snapshot --dataset injuries  --league-id 88 --season 2023 --snapshot-date 2026-11-08
uv run football-warehouse build-player-staging
```
Add `--team-id` for a snapshot of one team. The Airflow DAG does not run these steps yet.

| Staging table | One row per | Rebuilt |
| :--- | :--- | :--- |
| `stg_player_matches` | player and match | changed matches only, each replaced as a whole (`delete_insert`) |
| `stg_players` | player (latest profile) | fully |
| `stg_sidelined_players` | player whose absences were requested | fully |
| `stg_sidelined_periods` | absence period | fully |
| `stg_injuries` | player and match, latest snapshot of a league season | fully |

A reloaded match replaces all its rows, because `ReplacingMergeTree` alone would keep a player removed by a correction. The API sends `null` instead of zero for a player who played, so counting statistics become `0` for players with minutes in a match that has statistics, and stay `NULL` otherwise.

---

## 🔍 Source Data Limitations

API-Football is a live source with gaps. These findings are **preliminary**: they were measured on the free plan, mostly on samples from the 2023 season. They will be re-checked on the full data loaded with a paid plan, and the decisions below may change. They shape the planned scouting mart ([specification](docs/scouting_mart_spec.md)).

| Finding | Decision |
|---|---|
| `/injuries` returned no rows for Liga Portugal and the Belgian Pro League (2023 and 2024) | Injury availability comes from `/sidelined` for all four leagues, so players stay comparable |
| `/sidelined` covered 161 of 171 injury absences of 20 often injured Eredivisie players | Good enough as that single source; `/injuries` cross-checks it where it exists |
| `/sidelined` covered only 20 of 113 suspension absences in Eredivisie (18%) and 12 of 110 in EFL Championship (11%) | Suspended matches are counted from `/injuries` only and stay `NULL` elsewhere. Using the gaps would make players of two leagues look more disciplined. Deriving them from cards would need the rules of each league and cup matches that are not loaded. Cards per 90 minutes still measure discipline everywhere |
| `passes.accuracy` holds the number of accurate passes, not a percentage | The percentage is computed from it and `passes.total` |
| The `age` field of a player is the current age, even for a past season | Age is computed from the date of birth |

---

## 📌 Project Roadmap

- [x] Cloud infrastructure as code with Terraform (S3, IAM, S3 remote state with locking)
- [x] Ingestion CLI engine with rate-limiting, pagination, and S3 partitioning
- [x] Secure Docker container build with Astral uv and non-root user execution
- [x] Orchestration deployment via Docker Compose (Apache Airflow 3 & Kestra 2.0)
- [x] Bootstrap flows and DAGs for dimension tables extraction (Leagues, Teams)
- [ ] Scheduled daily batch ingestion flows for facts
- [x] Local ClickHouse deployment via Docker Compose
- [x] Batch loading from S3 into ClickHouse (fixtures, Airflow)
- [x] Fixtures staging built with dbt, with data tests
- [ ] Player match staging and scouting mart with dbt
- [ ] Interactive analytical dashboard (Metabase or Superset)
