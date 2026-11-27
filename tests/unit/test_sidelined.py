from pathlib import Path

import pytest
import yaml

from football_pipeline.services import sidelined

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"


def make_config(**settings):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"
    config["api"]["endpoints"]["sidelined"].update(settings)
    return config


def fake_services(monkeypatch, player_ids, respond=None):
    """Replaces S3 and the API. By default every player has one absence."""
    log = {"requests": [], "uploads": {}, "read": [], "waits": []}

    def fake_fetch_data(**kwargs):
        log["requests"].append(kwargs["query_params"])
        ids = [int(i) for i in kwargs["query_params"]["players"].split("-")]
        if respond:
            return {"response": respond(ids)}
        period = {"type": "Knock", "start": "2024-01-01", "end": None}
        return {"response": [{"id": i, "sidelined": [period]} for i in ids]}

    def fake_read(bucket, key):
        log["read"].append(key)
        return {"payload": {"response": [{"player": {"id": i}} for i in player_ids]}}

    monkeypatch.setattr(sidelined, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(sidelined, "read_json_from_s3", fake_read)
    monkeypatch.setattr(
        sidelined,
        "upload_to_s3",
        lambda data, bucket, key: log["uploads"].update({key: data}),
    )
    monkeypatch.setattr(sidelined.time, "sleep", log["waits"].append)
    return log


def run(config, **kwargs):
    arguments = {"league_id": 88, "season": 2023, **kwargs}
    sidelined.run_sidelined_pipeline(config, "2026-11-27", **arguments)


@pytest.mark.parametrize(("team_id", "partition"), [(None, ""), (194, "/team_id=194")])
def test_players_snapshot_and_result_share_the_filters(monkeypatch, team_id, partition):
    log = fake_services(monkeypatch, player_ids=[1])

    run(make_config(), team_id=team_id)

    suffix = f"league_id=88/season=2023{partition}/date=2026-11-27/data.json"
    assert log["read"] == [f"raw/facts/players_statistics/{suffix}"]
    assert list(log["uploads"]) == [f"raw/facts/sidelined/{suffix}"]


def test_players_are_requested_once_each_in_batches_into_one_snapshot(monkeypatch):
    log = fake_services(monkeypatch, player_ids=[3, 1, 2, 3, 5, 4])

    run(make_config(batch_size=2))

    assert log["requests"] == [
        {"players": "1-2"},
        {"players": "3-4"},
        {"players": "5"},
    ]
    assert log["waits"] == [7, 7]
    (envelope,) = log["uploads"].values()
    assert envelope["payload"]["results"] == 5
    assert [item["id"] for item in envelope["payload"]["response"]] == [1, 2, 3, 4, 5]


def test_requested_players_without_absences_are_recorded(monkeypatch):
    log = fake_services(
        monkeypatch,
        player_ids=[1, 2],
        respond=lambda ids: [{"id": 1, "sidelined": []}],
    )

    run(make_config())

    (envelope,) = log["uploads"].values()
    assert envelope["_metadata"]["params"]["players"] == [1, 2]
    assert envelope["payload"]["results"] == 1


def test_a_failed_batch_stores_nothing(monkeypatch):
    def respond(ids):
        if ids == [3]:
            raise ValueError("API returned errors")
        return [{"id": i, "sidelined": []} for i in ids]

    log = fake_services(monkeypatch, player_ids=[1, 2, 3], respond=respond)

    with pytest.raises(ValueError, match="API returned errors"):
        run(make_config(batch_size=2))

    assert log["uploads"] == {}


@pytest.mark.parametrize(
    ("player_ids", "message"),
    [([], "No players"), ([1], "no absence periods")],
)
def test_an_empty_result_is_not_stored(monkeypatch, player_ids, message):
    log = fake_services(monkeypatch, player_ids=player_ids, respond=lambda ids: [])

    with pytest.raises(ValueError, match=message):
        run(make_config())

    assert log["uploads"] == {}


@pytest.mark.parametrize(
    ("settings", "arguments"),
    [({"batch_size": 0}, {}), ({"batch_size": 21}, {}), ({}, {"season": None})],
)
def test_invalid_input_fails_before_any_request(monkeypatch, settings, arguments):
    log = fake_services(monkeypatch, player_ids=[1])

    with pytest.raises(ValueError):
        run(make_config(**settings), **arguments)

    assert log["read"] == []
    assert log["requests"] == []
