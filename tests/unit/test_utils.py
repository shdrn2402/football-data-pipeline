import pytest

from utils import build_s3_key


def test_build_s3_key_basic():
    result = build_s3_key(template_string="landing/{endpoint}", endpoint="leagues")
    assert result == "landing/leagues/data.json"


def test_build_s3_key_with_sorted_extra_params():
    result = build_s3_key(
        template_string="landing/{endpoint}", endpoint="fixtures", team=33, season=2024
    )
    # Параметры должны быть отсортированы по алфавиту: season=2024/team=33
    assert result == "landing/fixtures/season=2024/team=33/data.json"


def test_build_s3_key_ignores_target_date():
    result = build_s3_key(
        template_string="landing/{endpoint}",
        endpoint="teams",
        target_date="2024-10-15",
        league=39,
    )
    assert result == "landing/teams/league=39/data.json"


def test_build_s3_key_missing_template_placeholder():
    with pytest.raises(KeyError):
        build_s3_key(template_string="landing/{missing_param}", endpoint="leagues")
