import logging
import time

from football_pipeline.domain.schemas import DataEnvelope, Metadata
from football_pipeline.extractors.football_api import fetch_data
from football_pipeline.storage.s3 import (
    add_filter_partitions,
    build_s3_key,
    read_json_from_s3,
    upload_to_s3,
)

logger = logging.getLogger(__name__)

ENDPOINT = "sidelined"
# The API limit of the "players" parameter.
MAX_BATCH_SIZE = 20


def build_key(config: dict, endpoint: str, filters: dict, snapshot_date: str) -> str:
    """Builds the snapshot key of an endpoint for a league, season and optional team."""
    template = config["api"]["endpoints"][endpoint]["s3_template"]
    return build_s3_key(
        add_filter_partitions(template, filters),
        snapshot_date=snapshot_date,
        **filters,
    )


def run_sidelined_pipeline(
    config: dict,
    snapshot_date: str,
    league_id: int | None = None,
    season: int | None = None,
    team_id: int | None = None,
) -> None:
    """
    Downloads the absence periods of a league season's players to one S3 snapshot.

    The players come from the players_statistics snapshot of the same date. Nothing
    is stored unless every batch succeeds, as a partial snapshot would look complete.
    The requested IDs are kept in the metadata: the API omits players without any
    absence, so only that list tells them from players never asked about.

    Args:
        config (dict): Application configuration with secrets.
        snapshot_date (str): Date of the players snapshot to read and of the result.
        league_id (int | None): League of the snapshot.
        season (int | None): Season of the snapshot.
        team_id (int | None): Reads and writes the snapshot of one team.

    Raises:
        ValueError: If filters or settings are invalid, the players snapshot is
            empty, or the API returns no periods at all.
    """
    if league_id is None or season is None:
        raise ValueError(f"'{ENDPOINT}' needs a league and a season.")
    endpoint_config = config["api"]["endpoints"][ENDPOINT]
    batch_size = endpoint_config["batch_size"]
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be from 1 to {MAX_BATCH_SIZE}.")

    limits = config["api"]["limits"]
    bucket = config["aws_s3_landing_bucket"]
    filters = {"league": league_id, "season": season}
    if team_id is not None:
        filters["team"] = team_id

    players_key = build_key(config, "players_statistics", filters, snapshot_date)
    snapshot = read_json_from_s3(bucket, players_key)
    player_ids = sorted(
        {item["player"]["id"] for item in snapshot["payload"]["response"]}
    )
    if not player_ids:
        raise ValueError(f"No players in snapshot {players_key}.")

    batches = [
        player_ids[start : start + batch_size]
        for start in range(0, len(player_ids), batch_size)
    ]
    logger.info(f"Requesting {len(player_ids)} players in {len(batches)} requests.")

    records = []
    for number, batch in enumerate(batches):
        if number:
            time.sleep(limits["delay_seconds"])
        response = fetch_data(
            url=config["api"]["base_url"] + endpoint_config["path"],
            headers={config["api"]["headers"]["key_name"]: config["api_football_key"]},
            timeout=(limits["timeout_connect"], limits["timeout_read"]),
            query_params={"players": "-".join(str(item) for item in batch)},
            delay_seconds=limits["delay_seconds"],
            max_retries=limits["max_retries"],
            retry_delay_seconds=limits["retry_delay_seconds"],
        )
        records.extend(response["response"])

    if not records:
        raise ValueError("The API returned no absence periods for any player.")
    # Shows whether the source is still being updated.
    newest = max(
        (
            period["start"]
            for item in records
            for period in item["sidelined"]
            if period["start"]
        ),
        default=None,
    )
    logger.info(
        f"{len(records)} of {len(player_ids)} players have absence periods, "
        f"the newest one starts on {newest}."
    )

    envelope = DataEnvelope(
        _metadata=Metadata(
            endpoint=ENDPOINT,
            params={**filters, "players": player_ids},
            snapshot_date=snapshot_date,
        ),
        payload={"get": ENDPOINT, "results": len(records), "response": records},
    )
    s3_key = build_key(config, ENDPOINT, filters, snapshot_date)
    upload_to_s3(envelope.model_dump(by_alias=True, mode="json"), bucket, s3_key)
    logger.info(f"Data successfully uploaded to S3 bucket '{bucket}' at '{s3_key}'.")
