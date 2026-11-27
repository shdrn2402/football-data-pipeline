from pathlib import Path

import pytest
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
        return {"response": [{"fixture": {"id": 1}}]}

    def fake_upload_to_s3(data, bucket, s3_key):
        captured["s3_key"] = s3_key

    monkeypatch.setattr(ingestion, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(ingestion, "upload_to_s3", fake_upload_to_s3)

    ingestion.run_ingestion_pipeline(
        endpoint="fixtures",
        snapshot_date="2026-11-07",
        config=config,
        league_id=39,
        season=2023,
    )

    # A "date" filter would limit the response to matches played on snapshot_date.
    assert captured["query_params"] == {"league": 39, "season": 2023}
    assert (
        captured["s3_key"]
        == "raw/facts/fixtures/league_id=39/season=2023/date=2026-11-07/data.json"
    )


def test_failed_fetch_does_not_upload_to_s3(monkeypatch):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"

    uploads = []

    def fake_fetch_data(**kwargs):
        raise ValueError("API returned errors")

    monkeypatch.setattr(ingestion, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(ingestion, "upload_to_s3", lambda *args: uploads.append(args))

    with pytest.raises(ValueError):
        ingestion.run_ingestion_pipeline(
            endpoint="fixtures",
            snapshot_date="2026-11-07",
            config=config,
            league_id=39,
            season=2023,
        )

    assert uploads == []


@pytest.mark.parametrize(
    ("endpoint", "uploads_expected"),
    [("fixtures", 0), ("injuries", 1)],
)
def test_empty_response_is_uploaded_only_if_allowed(
    monkeypatch, endpoint, uploads_expected
):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"

    uploads = []

    monkeypatch.setattr(ingestion, "fetch_data", lambda **kwargs: {"response": []})
    monkeypatch.setattr(ingestion, "upload_to_s3", lambda *args: uploads.append(args))

    def run():
        ingestion.run_ingestion_pipeline(
            endpoint=endpoint,
            snapshot_date="2026-11-07",
            config=config,
            league_id=39,
            season=2023,
        )

    if uploads_expected:
        run()
    else:
        with pytest.raises(ValueError, match="Empty API response"):
            run()

    assert len(uploads) == uploads_expected


@pytest.mark.parametrize(
    ("endpoint", "filters", "expected_key"),
    [
        (
            "fixtures",
            {"team_id": 33},
            "raw/facts/fixtures/league_id=39/season=2023/team_id=33/date=2026-11-07",
        ),
        (
            "standings",
            {"team_id": 33},
            "raw/facts/standings/league_id=39/season=2023/team_id=33/date=2026-11-07",
        ),
        (
            "players_statistics",
            {"team_id": 33, "player_id": 276},
            (
                "raw/facts/players_statistics/league_id=39/season=2023/"
                "team_id=33/player_id=276/date=2026-11-07"
            ),
        ),
        (
            "fixtures_events",
            {"fixture_id": 1035037, "player_id": 276},
            "raw/facts/fixtures_events/fixture_id=1035037/player_id=276",
        ),
        (
            "transfers",
            {"team_id": 33},
            "raw/facts/transfers/team_id=33/date=2026-11-07",
        ),
        (
            "transfers",
            {"player_id": 276},
            "raw/facts/transfers/player_id=276/date=2026-11-07",
        ),
        (
            "teams_statistics",
            {"team_id": 33},
            (
                "raw/facts/teams_statistics/league_id=39/season=2023/"
                "team_id=33/date=2026-11-07"
            ),
        ),
    ],
)
def test_filters_are_part_of_s3_key(monkeypatch, endpoint, filters, expected_key):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"

    keys = []

    monkeypatch.setattr(
        ingestion, "fetch_data", lambda **kwargs: {"response": [{"id": 1}]}
    )
    monkeypatch.setattr(
        ingestion, "upload_to_s3", lambda data, bucket, key: keys.append(key)
    )

    ingestion.run_ingestion_pipeline(
        endpoint=endpoint,
        snapshot_date="2026-11-07",
        config=config,
        league_id=39,
        season=2023,
        **filters,
    )

    assert keys == [f"{expected_key}/data.json"]


@pytest.mark.parametrize(
    "endpoint",
    [
        "teams_statistics",
        "fixtures_events",
        "fixtures_head_to_head",
        "players_squads",
        "transfers",
    ],
)
def test_missing_key_value_fails_before_api_call(monkeypatch, endpoint):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"

    requests_made = []

    monkeypatch.setattr(
        ingestion, "fetch_data", lambda **kwargs: requests_made.append(kwargs)
    )

    with pytest.raises((KeyError, ValueError)):
        ingestion.run_ingestion_pipeline(
            endpoint=endpoint,
            snapshot_date="2026-11-07",
            config=config,
            league_id=39,
            season=2023,
        )

    assert requests_made == []


@pytest.mark.parametrize(
    ("endpoint", "kwargs", "expected_params"),
    [
        ("injuries", {"league_id": 88, "season": 2023}, {"league": 88, "season": 2023}),
        ("fixtures_head_to_head", {"h2h": "33-34"}, {"h2h": "33-34"}),
        (
            "teams_statistics",
            {"league_id": 88, "season": 2023, "team_id": 200},
            {"league": 88, "season": 2023, "team": 200, "date": "2026-11-07"},
        ),
    ],
)
def test_snapshot_date_is_sent_only_where_it_does_not_narrow(
    monkeypatch, endpoint, kwargs, expected_params
):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"

    sent = []

    def fake_fetch_data(**request):
        sent.append(request["query_params"])
        return {"response": [{"id": 1}]}

    monkeypatch.setattr(ingestion, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(ingestion, "upload_to_s3", lambda *args: None)

    ingestion.run_ingestion_pipeline(
        endpoint=endpoint, snapshot_date="2026-11-07", config=config, **kwargs
    )

    assert sent == [expected_params]
