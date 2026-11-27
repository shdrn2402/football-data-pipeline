from pathlib import Path

import pytest
import yaml

from football_pipeline.services import match_details

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"


def make_config(**settings):
    config = yaml.safe_load(CONFIG_PATH.read_text())
    config["api_football_key"] = "test-key"
    config["aws_s3_landing_bucket"] = "test-bucket"
    config["api"]["endpoints"]["match_details"].update(settings)
    return config


def key_of(fixture_id):
    return f"raw/facts/match_details/fixture_id={fixture_id}/data.json"


def details(fixture_id, **sections):
    item = {name: [{}] for name in match_details.DETAIL_SECTIONS}
    return {**item, "fixture": {"id": fixture_id}, **sections}


def fake_services(monkeypatch, fixtures=(), stored=(), respond=None):
    """Replaces S3 and the API. Fixtures are (id, status, date) tuples."""
    log = {"requests": [], "uploads": {}, "read": [], "waits": []}
    snapshot = {
        "payload": {
            "response": [
                {"fixture": {"id": i, "status": {"short": status}, "date": date}}
                for i, status, date in fixtures
            ]
        }
    }

    def fake_fetch_data(**kwargs):
        params = kwargs["query_params"]
        log["requests"].append(params)
        ids = [int(i) for i in str(params.get("id", params.get("ids"))).split("-")]
        items = respond(ids) if respond else [details(i) for i in ids]
        return {"get": "fixtures", "results": len(items), "response": items}

    def fake_read(bucket, key):
        log["read"].append(key)
        return snapshot

    monkeypatch.setattr(match_details, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(match_details, "read_json_from_s3", fake_read)
    monkeypatch.setattr(
        match_details,
        "list_s3_keys",
        lambda bucket, prefix: {key_of(i) for i in stored},
    )
    monkeypatch.setattr(
        match_details,
        "upload_to_s3",
        lambda data, bucket, key: log["uploads"].update({key: data}),
    )
    monkeypatch.setattr(match_details.time, "sleep", log["waits"].append)
    return log


def run(config, **kwargs):
    arguments = {"league_id": 88, "season": 2023, **kwargs}
    match_details.run_match_details_pipeline(config, "2026-11-27", **arguments)


SEASON = [
    (3, "PEN", "2023-08-13"),
    (1, "FT", "2023-08-11"),
    (4, "PST", "2023-08-11"),
    (5, "NS", "2024-05-01"),
    (2, "AET", "2023-08-12"),
    (6, "FT", "2023-08-14"),
]


def test_only_finished_matches_that_are_not_stored_are_requested(monkeypatch):
    log = fake_services(monkeypatch, fixtures=SEASON, stored=[2])

    run(make_config())

    assert log["read"] == [
        "raw/facts/fixtures/league_id=88/season=2023/date=2026-11-27/data.json"
    ]
    assert log["requests"] == [{"id": 1}, {"id": 3}, {"id": 6}]
    assert list(log["uploads"]) == [key_of(1), key_of(3), key_of(6)]
    assert log["waits"] == [7, 7]


@pytest.mark.parametrize(
    ("max_fixtures", "expected"),
    [(None, [{"id": 1}, {"id": 2}]), (1, [{"id": 1}])],
)
def test_matches_per_run_are_limited(monkeypatch, max_fixtures, expected):
    log = fake_services(monkeypatch, fixtures=SEASON)

    run(make_config(max_fixtures_per_run=2), max_fixtures=max_fixtures)

    assert log["requests"] == expected


def test_a_batch_is_stored_as_one_object_per_match(monkeypatch):
    log = fake_services(monkeypatch, fixtures=SEASON)

    run(make_config(batch_size=3))

    assert log["requests"] == [{"ids": "1-2-3"}, {"ids": "6"}]
    assert list(log["uploads"]) == [key_of(i) for i in (1, 2, 3, 6)]
    envelope = log["uploads"][key_of(2)]
    assert envelope["payload"]["results"] == 1
    assert envelope["payload"]["response"] == [details(2)]
    assert envelope["_metadata"]["params"] == {"ids": "1-2-3"}


def test_a_given_fixture_is_downloaded_even_if_stored(monkeypatch):
    log = fake_services(monkeypatch, stored=[2])

    run(make_config(), league_id=None, season=None, fixture_id=2)

    assert log["read"] == []
    assert list(log["uploads"]) == [key_of(2)]


def test_nothing_is_requested_when_every_match_is_stored(monkeypatch):
    log = fake_services(monkeypatch, fixtures=SEASON, stored=[1, 2, 3, 6])

    run(make_config())

    assert log["requests"] == []


def test_a_match_missing_in_the_response_fails_after_storing_the_rest(monkeypatch):
    log = fake_services(
        monkeypatch, fixtures=SEASON, respond=lambda ids: [details(ids[0])]
    )

    with pytest.raises(ValueError, match=r"no data for fixtures: \[2, 3\]"):
        run(make_config(batch_size=3))

    assert list(log["uploads"]) == [key_of(1)]


def test_a_response_without_a_detail_section_is_not_stored(monkeypatch):
    def respond(ids):
        item = details(ids[0])
        del item["players"]
        return [item]

    log = fake_services(monkeypatch, fixtures=SEASON, respond=respond)

    with pytest.raises(ValueError, match="players"):
        run(make_config())

    assert log["uploads"] == {}


def test_an_empty_detail_section_is_stored(monkeypatch):
    log = fake_services(
        monkeypatch, respond=lambda ids: [details(ids[0], statistics=[])]
    )

    run(make_config(), fixture_id=2)

    assert list(log["uploads"]) == [key_of(2)]


@pytest.mark.parametrize(
    ("settings", "arguments"),
    [
        ({"batch_size": 0}, {}),
        ({"batch_size": 21}, {}),
        ({}, {"max_fixtures": 0}),
        ({}, {"season": None}),
    ],
)
def test_invalid_input_fails_before_any_request(monkeypatch, settings, arguments):
    log = fake_services(monkeypatch, fixtures=SEASON)

    with pytest.raises(ValueError):
        run(make_config(**settings), **arguments)

    assert log["requests"] == []
