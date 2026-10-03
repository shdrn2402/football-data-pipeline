import os
from datetime import UTC, datetime
from pathlib import Path

import click

from football_pipeline.core.config import load_config
from football_pipeline.core.logger import setup_logger
from football_pipeline.services.ingestion import run_ingestion_pipeline


@click.command()
@click.option(
    "--endpoint",
    type=click.Choice(
        [
            "leagues",
            "teams",
            "teams_statistics",
            "standings",
            "fixtures",
            "fixtures_rounds",
            "fixtures_head_to_head",
            "fixtures_statistics",
            "fixtures_events",
            "fixtures_lineups",
            "fixtures_players",
            "players_statistics",
            "players_squads",
            "injuries",
            "transfers",
        ],
        case_sensitive=False,
    ),
    default="fixtures",
    required=True,
    envvar="INGEST_ENDPOINT",
    help="Choose the API endpoint to ingest data from.",
)
@click.option(
    "--league-id",
    default=39,
    type=int,
    envvar="INGEST_LEAGUE_ID",
    help="Specify the league ID for which to ingest data. Default is 39.",
)
@click.option(
    "--season",
    default=2024,
    type=int,
    envvar="INGEST_SEASON",
    help="Specify the season year (format YYYY) for which to ingest data. Default is 2024.",
)
@click.option(
    "--team-id",
    default=None,
    type=int,
    envvar="INGEST_TEAM_ID",
    help="Specify the team ID to filter data for a specific team.",
)
@click.option(
    "--h2h",
    default=None,
    type=str,
    envvar="INGEST_H2H",
    help="Specify the head-to-head team IDs (hyphen-separated) to filter data.",
)
@click.option(
    "--fixture-id",
    default=None,
    type=int,
    envvar="INGEST_FIXTURE_ID",
    help="Specify the fixture ID to filter data for a specific match.",
)
@click.option(
    "--player-id",
    default=None,
    type=int,
    envvar="INGEST_PLAYER_ID",
    help="Specify the player ID to filter data for a specific player.",
)
@click.option(
    "--target-date",
    default=datetime.now(UTC).strftime("%Y-%m-%d"),
    type=str,
    envvar="INGEST_TARGET_DATE",
    help="Specify the logical date for the data ingestion process. Default is current UTC date.",
)
def cli(
    endpoint: str,
    league_id: int,
    season: int,
    team_id: int | None,
    h2h: str | None,
    fixture_id: int | None,
    player_id: int | None,
    target_date: str,
) -> None:
    """Entry point for the data ingestion pipeline."""
    setup_logger()

    root_path = Path(__file__).resolve().parent.parent.parent
    default_config_path = root_path / "configs" / "config.yaml"
    default_env_path = root_path / ".env"

    config_path = os.environ.get("PIPELINE_CONFIG_PATH", default_config_path)
    env_path = os.environ.get("PIPELINE_ENV_PATH", default_env_path)

    config = load_config(config_path, env_path)

    run_ingestion_pipeline(
        endpoint=endpoint,
        target_date=target_date,
        config=config,
        league_id=league_id,
        season=season,
        team_id=team_id,
        h2h=h2h,
        fixture_id=fixture_id,
        player_id=player_id,
    )


if __name__ == "__main__":
    cli()
