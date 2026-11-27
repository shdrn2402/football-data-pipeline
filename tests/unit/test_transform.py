import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from football_pipeline.warehouse import transform


@pytest.mark.parametrize("succeeded", [True, False])
def test_build_staging_passes_the_snapshot_and_fails_with_dbt(monkeypatch, succeeded):
    calls = []
    monkeypatch.setenv("DBT_TARGET_PATH", "unused")
    monkeypatch.setenv("DBT_LOG_PATH", "unused")
    monkeypatch.setattr(
        transform, "run_dbt", lambda arguments: calls.append(arguments) or succeeded
    )

    if succeeded:
        transform.build_staging(88, 2023, "2026-11-27")
    else:
        with pytest.raises(RuntimeError, match="dbt build failed"):
            transform.build_staging(88, 2023, "2026-11-27")

    (arguments,) = calls
    assert arguments[0] == "build"
    assert json.loads(arguments[arguments.index("--vars") + 1]) == {
        "league_id": 88,
        "season": 2023,
        "snapshot_date": "2026-11-27",
    }


def test_dbt_runs_outside_a_directory_with_an_env_file(monkeypatch, tmp_path):
    calls = {}

    def fake_run(command, cwd, check):
        calls.update(command=command, cwd=cwd)
        return subprocess.CompletedProcess(command, returncode=0)

    monkeypatch.setattr(transform, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(transform.subprocess, "run", fake_run)

    assert transform.run_dbt(["build"])

    assert calls["command"][-3:] == ["-m", "dbt.cli.main", "build"]
    assert calls["cwd"] == tmp_path / "work"
    assert not (calls["cwd"] / ".env").exists()


def test_importing_the_warehouse_cli_does_not_load_a_local_env_file(tmp_path):
    (tmp_path / ".env").write_text("PROBE_VARIABLE=leaked\n")
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[2] / "src"),
    }
    environment.pop("PROBE_VARIABLE", None)
    code = (
        "import os, football_pipeline.warehouse.cli; "
        "print(os.environ.get('PROBE_VARIABLE'))"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "None"
