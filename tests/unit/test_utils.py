import pytest

from utils import build_s3_key


@pytest.mark.parametrize(
    ("template_string", "kwargs", "expected_key"),
    [
        # Dimensions (Bootstrap)
        (
            "raw/dimensions/leagues/league_id={id}",
            {"id": 39, "season": 2024, "target_date": "2026-10-02", "team": None},
            "raw/dimensions/leagues/league_id=39/data.json",
        ),
        (
            "raw/dimensions/teams/league_id={league}/season={season}",
            {"league": 39, "season": 2024, "target_date": "2026-10-02"},
            "raw/dimensions/teams/league_id=39/season=2024/data.json",
        ),
        # Facts with target_date (SCD / Periodic Snapshots)
        (
            "raw/facts/players_squads/team_id={team}/date={target_date}",
            {"team": 33, "league": 39, "season": 2024, "target_date": "2026-10-02"},
            "raw/facts/players_squads/team_id=33/date=2026-10-02/data.json",
        ),
        (
            "raw/facts/transfers/team_id={team}/date={target_date}",
            {"team": 33, "target_date": "2026-10-02", "league": 39, "season": 2024},
            "raw/facts/transfers/team_id=33/date=2026-10-02/data.json",
        ),
        (
            "raw/facts/standings/league_id={league}/season={season}/date={target_date}",
            {"league": 39, "season": 2024, "target_date": "2026-10-02"},
            "raw/facts/standings/league_id=39/season=2024/date=2026-10-02/data.json",
        ),
        # Immutable Facts (No date)
        (
            "raw/facts/fixtures_statistics/fixture_id={fixture}",
            {"fixture": 1035001, "target_date": "2026-10-02", "league": 39},
            "raw/facts/fixtures_statistics/fixture_id=1035001/data.json",
        ),
        (
            "raw/facts/fixtures/league_id={league}/season={season}/date={target_date}",
            {
                "league": 39,
                "season": 2024,
                "target_date": "2026-10-02",
                "team": 33,  # Extra parameter not in template must be ignored
            },
            "raw/facts/fixtures/league_id=39/season=2024/date=2026-10-02/data.json",
        ),
    ],
)
def test_build_s3_key_deterministic(template_string, kwargs, expected_key):
    assert build_s3_key(template_string, **kwargs) == expected_key


def test_build_s3_key_missing_placeholder():
    with pytest.raises(KeyError):
        build_s3_key("raw/facts/fixtures_statistics/fixture_id={fixture}")
