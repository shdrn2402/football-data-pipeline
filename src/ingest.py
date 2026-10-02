import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
from pydantic import ValidationError

from schemas import DataEnvelope, Metadata
from utils import build_s3_key, fetch_data, load_config, upload_to_s3

# Configure the root logger for the entire project
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--endpoint",
    type=click.Choice(
        [
            "fixtures",
            "fixtures_events",
            "fixtures_head_to_head",
            "fixtures_lineups",
            "fixtures_players",
            "fixtures_rounds",
            "fixtures_statistics",
            "injuries",
            "leagues",
            "players_profiles",
            "players_seasons",
            "players_squads",
            "players_statistics",
            "players_teams",
            "players_top_assists",
            "players_top_redcards",
            "players_top_scorers",
            "players_top_yellowcards",
            "standings",
            "teams",
            "teams_seasons",
            "teams_statistics",
            "transfers",
        ],
        case_sensitive=False,
    ),
    default="fixtures",
    required=True,
    envvar="INGEST_ENDPOINT",
    help="Choose the API endpoint to ingest data from. Options: fixtures, teams, players, transfers.",
)
@click.option(
    "--league-id",
    default=39,  # Default to English Premier League
    type=int,
    envvar="INGEST_LEAGUE_ID",
    help="Specify the league ID for which to ingest data. Default is 39 (English Premier League).",
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
    help="Specify the head-to-head team IDs (hyphen-separated) to filter data for specific matchups.",
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
    help="Specify the logical date for the data ingestion process. Default is the current UTC date.",
)
def ingest_data(
    endpoint: str,
    league_id: int,
    season: int,
    team_id: int | None,
    h2h: str | None,
    fixture_id: int | None,
    player_id: int | None,
    target_date: str | None,
) -> None:

    # Loading configuration and environment variables
    # Dynamically resolve the absolute path to the project root
    root_path = Path(__file__).resolve().parent.parent
    # Idiomatic path construction using the slash operator
    config_path = root_path / "configs" / "config.yaml"
    env_path = root_path / ".env"

    config = load_config(config_path, env_path)
    safe_config = {
        k: ("***" if "key" in k.lower() or "secret" in k.lower() else v)
        for k, v in config.items()
    }
    logger.info(f"Configuration successfully loaded: {safe_config}")

    # Retrieving a RAW data payload from the API
    endpoint_config = config["api"]["endpoints"][endpoint]
    url = config["api"]["base_url"] + endpoint_config["path"]
    headers = {config["api"]["headers"]["key_name"]: config["api_football_key"]}
    timeout = (
        config["api"]["limits"]["timeout_connect"],
        config["api"]["limits"]["timeout_read"],
    )
    delay_seconds = config["api"]["limits"]["delay_seconds"]

    all_args = {
        "id": league_id,
        "league": league_id,
        "season": season,
        "team": team_id,
        "h2h": h2h,
        "fixture": fixture_id,
        "player": player_id,
    }
    query_params = {}
    for el in endpoint_config["allowed_params"]:
        val = all_args.get(el)
        if val is not None:
            query_params[el] = val

    raw_data = fetch_data(
        url=url,
        headers=headers,
        timeout=timeout,
        query_params=query_params,
        delay_seconds=delay_seconds,
    )
    logger.info(f"Data successfully fetched. Payload snippet: {str(raw_data)[:300]}...")

    try:
        envelope = DataEnvelope(
            _metadata=Metadata(
                endpoint=endpoint,
                params=query_params,
                target_date=target_date,
            ),
            payload=raw_data,
        )
        validated_dict = envelope.model_dump(by_alias=True, mode="json")
    except ValidationError as e:
        logger.error(f"Payload validation failed: {e}")
        raise

    validated_dict = envelope.model_dump(by_alias=True, mode="json")

    # Uploading the RAW data to S3
    bucket_name = config["aws_s3_landing_bucket"]
    s3_key = build_s3_key(
        template_string=endpoint_config["s3_template"],
        target_date=target_date,
        **query_params,
    )

    upload_to_s3(validated_dict, bucket_name, s3_key)
    logger.info(
        f"Data successfully uploaded to S3 bucket '{bucket_name}' at '{s3_key}'."
    )


if __name__ == "__main__":
    ingest_data()
