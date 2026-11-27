import os
from pathlib import Path

import pytest

from football_pipeline.core import config as config_module
from football_pipeline.core.config import load_config, load_env

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "config.yaml"


@pytest.mark.parametrize(("override", "expected"), [("0.5", 0.5), ("", 7), (None, 7)])
def test_api_delay_can_be_overridden(monkeypatch, tmp_path, override, expected):
    monkeypatch.setenv("API_FOOTBALL_KEY", "test-key")
    monkeypatch.setenv("AWS_S3_LANDING_BUCKET_NAME", "test-bucket")
    if override is None:
        monkeypatch.delenv("API_DELAY_SECONDS", raising=False)
    else:
        monkeypatch.setenv("API_DELAY_SECONDS", override)

    config = load_config(CONFIG_PATH, tmp_path / "missing.env")

    assert config["api"]["limits"]["delay_seconds"] == expected


@pytest.fixture
def unset_env(monkeypatch):
    """Unsets variables and restores them after the test, even if load_env set them."""

    def unset(*names):
        for name in names:
            monkeypatch.setenv(name, "")
            monkeypatch.delenv(name)

    return unset


def test_load_env_reads_the_file_named_by_pipeline_env_path(
    monkeypatch, tmp_path, unset_env
):
    env_file = tmp_path / ".env.local"
    env_file.write_text("NEW_VARIABLE=from-file\nSET_VARIABLE=from-file\n")
    unset_env("NEW_VARIABLE")
    monkeypatch.setenv("SET_VARIABLE", "from-environment")
    monkeypatch.setenv("PIPELINE_ENV_PATH", str(env_file))

    load_env()

    assert os.environ["NEW_VARIABLE"] == "from-file"
    assert os.environ["SET_VARIABLE"] == "from-environment"


@pytest.mark.parametrize("override", ["", None])
def test_load_env_falls_back_to_the_project_env_file(
    monkeypatch, tmp_path, unset_env, override
):
    env_file = tmp_path / ".env"
    env_file.write_text("NEW_VARIABLE=from-file\n")
    unset_env("NEW_VARIABLE", "PIPELINE_ENV_PATH")
    if override is not None:
        monkeypatch.setenv("PIPELINE_ENV_PATH", override)
    monkeypatch.setattr(config_module, "DEFAULT_ENV_PATH", env_file)

    load_env()

    assert os.environ["NEW_VARIABLE"] == "from-file"
