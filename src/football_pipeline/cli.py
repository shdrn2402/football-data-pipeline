from datetime import UTC, datetime

import click

from football_pipeline.core.config import load_config
from football_pipeline.core.logger import setup_logger
from football_pipeline.services.ingestion import run_ingestion_pipeline
from football_pipeline.services.match_details import (
    ENDPOINT as MATCH_DETAILS,
)
from football_pipeline.services.match_details import run_match_details_pipeline
from football_pipeline.services.sidelined import ENDPOINT as SIDELINED
from football_pipeline.services.sidelined import run_sidelined_pipeline


@click.command()
@click.option(
    "--endpoint",
    type=str.lower,
    default="fixtures",
    required=True,
    envvar="INGEST_ENDPOINT",
    help="API endpoint to ingest data from, as named in config.yaml.",
)
@click.option(
    "--league-id",
    default=None,
    type=int,
    envvar="INGEST_LEAGUE_ID",
    help="Specify the league ID for which to ingest data.",
)
@click.option(
    "--season",
    default=None,
    type=int,
    envvar="INGEST_SEASON",
    help="Specify the season start year (format YYYY) for which to ingest data.",
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
    "--max-fixtures",
    default=None,
    type=click.IntRange(min=1),
    envvar="INGEST_MAX_FIXTURES",
    help="match_details only: matches to download in this run. Default is from config.yaml.",
)
@click.option(
    "--snapshot-date",
    default=datetime.now(UTC).strftime("%Y-%m-%d"),
    type=str,
    envvar="INGEST_SNAPSHOT_DATE",
    help="Date of the extraction snapshot, not of the matches. Default is current UTC date.",
)
def cli(
    endpoint: str,
    league_id: int | None,
    season: int | None,
    team_id: int | None,
    h2h: str | None,
    fixture_id: int | None,
    player_id: int | None,
    max_fixtures: int | None,
    snapshot_date: str,
) -> None:
    """Entry point for the data ingestion pipeline."""
    setup_logger()

    config = load_config()

    endpoints = config["api"]["endpoints"]
    if endpoint not in endpoints:
        raise click.BadParameter(
            f"'{endpoint}' is not one of: {', '.join(endpoints)}.",
            param_hint="'--endpoint'",
        )

    if endpoint == MATCH_DETAILS:
        run_match_details_pipeline(
            config=config,
            snapshot_date=snapshot_date,
            league_id=league_id,
            season=season,
            fixture_id=fixture_id,
            max_fixtures=max_fixtures,
        )
        return

    if endpoint == SIDELINED:
        run_sidelined_pipeline(
            config=config,
            snapshot_date=snapshot_date,
            league_id=league_id,
            season=season,
            team_id=team_id,
        )
        return

    run_ingestion_pipeline(
        endpoint=endpoint,
        snapshot_date=snapshot_date,
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
