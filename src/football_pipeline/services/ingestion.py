import logging

from pydantic import ValidationError

from football_pipeline.domain.schemas import DataEnvelope, Metadata
from football_pipeline.extractors.football_api import fetch_data
from football_pipeline.storage.s3 import build_s3_key, upload_to_s3

logger = logging.getLogger(__name__)


def run_ingestion_pipeline(
    endpoint: str, target_date: str, config: dict, **kwargs
) -> None:
    """
    Executes the end-to-end data ingestion process for a specific API endpoint.

    Coordinates data extraction from the external API, validates the payload
    against Pydantic schemas, and loads the validated data into AWS S3.

    Args:
        endpoint (str): The target API endpoint name (e.g., "leagues", "fixtures").
        target_date (str): Logical execution date in "YYYY-MM-DD" format.
        config (dict): Application configuration dictionary containing API credentials,
            endpoints metadata, and AWS settings.
        **kwargs: Optional query parameters for API filtering. Supported keys include:
            - league_id (int): ID of the league.
            - season (int): Year of the season (e.g., 2024).
            - team_id (int): ID of the team.
            - player_id (int): ID of the player.
            - fixture_id (int): ID of the match fixture.
            - h2h (str): Hyphen-separated team IDs for head-to-head statistics.

    Raises:
        ValidationError: If the API response fails Pydantic schema validation.
        Exception: Propagates network errors from fetch_data or Boto3 S3 upload errors.
    """
    endpoint_config = config["api"]["endpoints"][endpoint]
    url = config["api"]["base_url"] + endpoint_config["path"]
    headers = {config["api"]["headers"]["key_name"]: config["api_football_key"]}
    timeout = (
        config["api"]["limits"]["timeout_connect"],
        config["api"]["limits"]["timeout_read"],
    )
    delay_seconds = config["api"]["limits"]["delay_seconds"]

    league_id = kwargs.get("league_id")
    team_id = kwargs.get("team_id")
    player_id = kwargs.get("player_id")

    target_entity_id = (
        player_id
        if endpoint in ("players", "players_statistics")
        else team_id
        if endpoint == "teams"
        else league_id
    )

    all_args = {
        "date": target_date,
        "fixture": kwargs.get("fixture_id"),
        "h2h": kwargs.get("h2h"),
        "id": target_entity_id,
        "league": league_id,
        "player": player_id,
        "season": kwargs.get("season"),
        "team": team_id,
    }

    query_params = {
        key: all_args[key]
        for key in endpoint_config["allowed_params"]
        if all_args.get(key) is not None
    }

    raw_data = fetch_data(
        url=url,
        headers=headers,
        timeout=timeout,
        query_params=query_params,
        delay_seconds=delay_seconds,
    )

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

    bucket_name = config["aws_s3_landing_bucket"]
    s3_key = build_s3_key(
        template_string=endpoint_config["s3_template"],
        target_date=target_date,
        **all_args,
    )

    upload_to_s3(validated_dict, bucket_name, s3_key)
    logger.info(
        f"Data successfully uploaded to S3 bucket '{bucket_name}' at '{s3_key}'."
    )
