import pytest
import yaml

from football_pipeline.core.config import DEFAULT_CONFIG_PATH, read_config
from football_pipeline.services import ingestion
from football_pipeline.warehouse import clickhouse


@pytest.mark.parametrize(
    "template",
    [
        None,  # the template of the real config
        "another/layout/{league}/{season}/date={target_date}",
        # Ingestion appends a filter the template lacks, so the URL must too.
        "raw/facts/fixtures/league_id={league}/date={target_date}",
    ],
)
def test_build_fixtures_s3_url_matches_ingestion_key(monkeypatch, tmp_path, template):
    config = read_config(DEFAULT_CONFIG_PATH)
    if template:
        config["api"]["endpoints"]["fixtures"]["s3_template"] = template
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config))
    monkeypatch.setenv("PIPELINE_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("AWS_S3_LANDING_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-central-1")
    uploaded = []
    monkeypatch.setattr(ingestion, "fetch_data", lambda **kwargs: {"response": [{}]})
    monkeypatch.setattr(
        ingestion, "upload_to_s3", lambda data, bucket, key: uploaded.append(key)
    )
    config.update(api_football_key="test-key", aws_s3_landing_bucket="test-bucket")

    ingestion.run_ingestion_pipeline(
        "fixtures", "2026-11-07", config, league_id=39, season=2023
    )
    url = clickhouse.build_fixtures_s3_url(39, 2023, "2026-11-07")

    assert url == f"https://test-bucket.s3.eu-central-1.amazonaws.com/{uploaded[0]}"


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
