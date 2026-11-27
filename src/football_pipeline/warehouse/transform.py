import json
import logging
import os
import tempfile
from pathlib import Path

from dbt.cli.main import dbtRunner

logger = logging.getLogger(__name__)

DBT_DIR = Path(__file__).parent / "dbt"


def run_dbt(arguments: list[str]) -> bool:
    """Runs one dbt command and tells whether it succeeded."""
    return dbtRunner().invoke(arguments).success


def build_staging(league_id: int, season: int, snapshot_date: str) -> None:
    """Builds the staging models from one raw snapshot and runs their tests.

    Raises:
        RuntimeError: If a model or a data test fails.
        KeyError: If a required environment variable is missing.
    """
    # dbt writes its artifacts here, not into the source tree.
    work_dir = Path(tempfile.gettempdir()) / "dbt"
    os.environ.setdefault("DBT_TARGET_PATH", str(work_dir / "target"))
    os.environ.setdefault("DBT_LOG_PATH", str(work_dir / "logs"))

    variables = {
        "league_id": league_id,
        "season": season,
        "snapshot_date": snapshot_date,
    }
    succeeded = run_dbt(
        [
            "build",
            "--project-dir",
            str(DBT_DIR),
            "--profiles-dir",
            str(DBT_DIR),
            "--vars",
            json.dumps(variables),
        ]
    )
    if not succeeded:
        raise RuntimeError("dbt build failed. See the failed model or test above.")
    logger.info("Staging is built and its tests passed.")
