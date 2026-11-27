from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from football_pipeline import cli

CONFIG = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "configs" / "config.yaml").read_text()
)


def run_cli(monkeypatch, args):
    calls = []
    monkeypatch.setattr(cli, "setup_logger", lambda: None)
    monkeypatch.setattr(cli, "load_config", lambda *paths: CONFIG)
    monkeypatch.setattr(
        cli, "run_ingestion_pipeline", lambda **kwargs: calls.append(kwargs)
    )
    return CliRunner().invoke(cli.cli, args), calls


@pytest.mark.parametrize("endpoint", CONFIG["api"]["endpoints"])
def test_cli_accepts_every_configured_endpoint(monkeypatch, endpoint):
    result, calls = run_cli(monkeypatch, ["--endpoint", endpoint.upper()])

    assert result.exit_code == 0, result.output
    assert calls[0]["endpoint"] == endpoint


def test_cli_rejects_unknown_endpoint(monkeypatch):
    result, calls = run_cli(monkeypatch, ["--endpoint", "players"])

    assert result.exit_code == 2
    assert "is not one of" in result.output
    assert calls == []


def test_config_declares_only_parameters_the_pipeline_can_send():
    # Mirrors the arguments built in run_ingestion_pipeline.
    supported = {
        "date",
        "fixture",
        "h2h",
        "id",
        "league",
        "player",
        "season",
        "team",
    }

    for name, endpoint in CONFIG["api"]["endpoints"].items():
        assert set(endpoint["allowed_params"]) <= supported, name
