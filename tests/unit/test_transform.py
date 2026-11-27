import json

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
