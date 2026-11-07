from pathlib import Path

import yaml

from football_pipeline.services import ingestion

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"


def test_fixtures_request_covers_whole_season(monkeypatch):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"

    captured = {}

    def fake_fetch_data(**kwargs):
        captured["query_params"] = kwargs["query_params"]
        return {"response": []}

    def fake_upload_to_s3(data, bucket, s3_key):
        captured["s3_key"] = s3_key

    monkeypatch.setattr(ingestion, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(ingestion, "upload_to_s3", fake_upload_to_s3)

    ingestion.run_ingestion_pipeline(
        endpoint="fixtures",
        target_date="2026-11-07",
        config=config,
        league_id=39,
        season=2023,
    )

    # A "date" filter would limit the response to matches played on target_date.
    assert captured["query_params"] == {"league": 39, "season": 2023}
    assert (
        captured["s3_key"]
        == "raw/facts/fixtures/league_id=39/season=2023/date=2026-11-07/data.json"
    )
