from pathlib import Path

import pytest

from football_pipeline.core.config import load_config

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
