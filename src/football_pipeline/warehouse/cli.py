import click

from football_pipeline.core.config import load_env
from football_pipeline.core.logger import setup_logger
from football_pipeline.warehouse.clickhouse import (
    SNAPSHOT_DATASETS,
    build_team_points,
    load_fixtures,
    load_match_details,
    load_player_snapshot,
)
from football_pipeline.warehouse.transform import build_player_staging, build_staging


@click.group()
def cli() -> None:
    """Loads raw data from S3 into ClickHouse and builds data marts."""
    setup_logger()
    load_env()


@cli.command("load-fixtures")
@click.option("--league-id", required=True, type=int)
@click.option("--season", required=True, type=int)
@click.option("--snapshot-date", required=True, type=str, help="Snapshot date.")
def load_fixtures_command(league_id: int, season: int, snapshot_date: str) -> None:
    """Loads one fixtures snapshot from S3 into the raw table."""
    load_fixtures(league_id, season, snapshot_date)


@cli.command("build-staging")
@click.option("--league-id", required=True, type=int)
@click.option("--season", required=True, type=int)
@click.option("--snapshot-date", required=True, type=str, help="Snapshot date.")
def build_staging_command(league_id: int, season: int, snapshot_date: str) -> None:
    """Builds the dbt staging models from one raw snapshot and tests them."""
    build_staging(league_id, season, snapshot_date)


@cli.command("load-match-details")
def load_match_details_command() -> None:
    """Loads new and changed match details from S3 into the raw table."""
    load_match_details()


@cli.command("load-player-snapshot")
@click.option("--dataset", required=True, type=click.Choice(list(SNAPSHOT_DATASETS)))
@click.option("--league-id", required=True, type=int)
@click.option("--season", required=True, type=int)
@click.option("--snapshot-date", required=True, type=str, help="Snapshot date.")
@click.option("--team-id", type=int, help="Loads the snapshot of one team.")
def load_player_snapshot_command(
    dataset: str, league_id: int, season: int, snapshot_date: str, team_id: int | None
) -> None:
    """Loads one players, sidelined or injuries snapshot into its raw table."""
    load_player_snapshot(dataset, league_id, season, snapshot_date, team_id)


@cli.command("build-player-staging")
def build_player_staging_command() -> None:
    """Builds the dbt player staging models and tests them."""
    build_player_staging()


@cli.command("build-team-points")
@click.option("--league-id", required=True, type=int)
@click.option("--season", required=True, type=int)
def build_team_points_command(league_id: int, season: int) -> None:
    """Rebuilds the team points mart for one league and season."""
    build_team_points(league_id, season)


if __name__ == "__main__":
    cli()
