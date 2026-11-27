"""Integration tests use a real ClickHouse and a temporary database.

Skipped unless RUN_INTEGRATION_TESTS=1 and the CLICKHOUSE_* variables are set.
"""

import os

import pytest

from football_pipeline.warehouse import clickhouse

DATABASE = "dbt_integration_test"


def pytest_collection_modifyitems(items):
    if os.environ.get("RUN_INTEGRATION_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="needs a running ClickHouse")
    for item in items:
        if "integration" in item.path.parts:
            item.add_marker(skip)


@pytest.fixture
def database(monkeypatch):
    clickhouse.execute(f"DROP DATABASE IF EXISTS {DATABASE}")
    clickhouse.execute(f"CREATE DATABASE {DATABASE}")
    monkeypatch.setenv("CLICKHOUSE_DB", DATABASE)
    clickhouse.run_sql_file("create_tables.sql")
    yield
    clickhouse.execute(f"DROP DATABASE {DATABASE}")
