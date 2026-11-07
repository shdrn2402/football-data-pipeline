import pytest

from football_pipeline.warehouse import clickhouse


def test_build_fixtures_s3_url_matches_ingestion_key(monkeypatch):
    monkeypatch.setenv("AWS_S3_LANDING_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")

    url = clickhouse.build_fixtures_s3_url(39, 2023, "2026-11-07")

    assert url == (
        "https://test-bucket.s3.eu-central-1.amazonaws.com/raw/facts/fixtures/"
        "league_id=39/season=2023/date=2026-11-07/data.json"
    )


def test_read_statements_splits_create_tables():
    statements = clickhouse.read_statements("create_tables.sql")

    assert len(statements) == 3
    assert all("CREATE TABLE IF NOT EXISTS" in s for s in statements)


def test_load_fixtures_fails_on_empty_snapshot(monkeypatch):
    monkeypatch.setenv("AWS_S3_LANDING_BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(clickhouse, "run_sql_file", lambda *args, **kwargs: None)
    monkeypatch.setattr(clickhouse, "load_raw_snapshot", lambda *args: None)
    monkeypatch.setattr(clickhouse, "execute", lambda *args, **kwargs: "0")

    with pytest.raises(ValueError, match="No fixtures found"):
        clickhouse.load_fixtures(39, 2023, "2026-11-07")


def test_load_raw_snapshot_sends_escaped_keys_outside_params(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "se'cret")
    captured = {}

    def fake_execute(statement, params=None):
        captured.update(statement=statement, params=params)
        return ""

    monkeypatch.setattr(clickhouse, "execute", fake_execute)

    clickhouse.load_raw_snapshot({"s3_url": "https://example/data.json"})

    assert "'key-id', 'se\\'cret'" in captured["statement"]
    assert captured["params"] == {"s3_url": "https://example/data.json"}
