import click

from football_pipeline.core.config import load_env
from football_pipeline.core.logger import setup_logger
from football_pipeline.warehouse.clickhouse import build_team_points, load_fixtures
from football_pipeline.warehouse.transform import build_staging


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


@cli.command("build-team-points")
@click.option("--league-id", required=True, type=int)
@click.option("--season", required=True, type=int)
def build_team_points_command(league_id: int, season: int) -> None:
    """Rebuilds the team points mart for one league and season."""
    build_team_points(league_id, season)


if __name__ == "__main__":
    cli()
