import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from football_pipeline.warehouse.clickhouse import run_sql_file

logger = logging.getLogger(__name__)

DBT_DIR = Path(__file__).parent / "dbt"
# dbt writes its artifacts here, not into the source tree.
WORK_DIR = Path(tempfile.gettempdir()) / "dbt"
# "+" adds the sources of a model, so their tests run first.
PLAYER_MODELS = (
    "+stg_player_matches",
    "+stg_players",
    "+stg_sidelined_periods",
    "+stg_injuries",
)


def run_dbt(arguments: list[str]) -> bool:
    """Runs one dbt command and tells whether it succeeded.

    dbt runs as a separate process and is never imported here: on import it loads
    .env from the working directory, overriding the file chosen by load_env, and
    replaces the logging setup. The working directory therefore holds no .env.
    """
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "dbt.cli.main", *arguments]
    return subprocess.run(command, cwd=WORK_DIR, check=False).returncode == 0


def build_models(selection: tuple[str, ...], variables: dict | None = None) -> None:
    """Builds the selected dbt models and runs their tests.

    Raises:
        RuntimeError: If a model or a data test fails.
        KeyError: If a required environment variable is missing.
    """
    os.environ.setdefault("DBT_TARGET_PATH", str(WORK_DIR / "target"))
    os.environ.setdefault("DBT_LOG_PATH", str(WORK_DIR / "logs"))

    arguments = [
        "build",
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
        "--select",
        *selection,
    ]
    if variables:
        arguments += ["--vars", json.dumps(variables)]
    if not run_dbt(arguments):
        raise RuntimeError("dbt build failed. See the failed model or test above.")
    logger.info("Staging is built and its tests passed.")


def build_staging(league_id: int, season: int, snapshot_date: str) -> None:
    """Builds fixtures staging from one raw snapshot."""
    build_models(
        ("+stg_fixtures",),
        {"league_id": league_id, "season": season, "snapshot_date": snapshot_date},
    )


def build_player_staging() -> None:
    """Builds player staging from everything loaded into the raw player tables."""
    run_sql_file("create_tables.sql")
    build_models(PLAYER_MODELS)
