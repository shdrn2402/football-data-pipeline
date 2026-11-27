import logging
import time

from football_pipeline.domain.schemas import DataEnvelope, Metadata
from football_pipeline.extractors.football_api import fetch_data
from football_pipeline.storage.s3 import (
    build_s3_key,
    list_s3_keys,
    read_json_from_s3,
    upload_to_s3,
)

logger = logging.getLogger(__name__)

ENDPOINT = "match_details"
# The API limit of the "ids" parameter.
MAX_BATCH_SIZE = 20
DETAIL_SECTIONS = ("events", "lineups", "statistics", "players")


def select_finished_fixtures(snapshot: dict, finished_statuses: list[str]) -> list[int]:
    """Returns the IDs of finished matches of a fixtures snapshot, oldest first."""
    finished = [
        item["fixture"]
        for item in snapshot["payload"]["response"]
        if item["fixture"]["status"]["short"] in finished_statuses
    ]
    finished.sort(key=lambda fixture: (fixture["date"], fixture["id"]))
    return [fixture["id"] for fixture in finished]


def find_pending_fixtures(
    config: dict, league_id: int, season: int, target_date: str
) -> list[int]:
    """Returns finished matches of a snapshot whose details are not in S3 yet."""
    endpoints = config["api"]["endpoints"]
    bucket = config["aws_s3_landing_bucket"]
    template = endpoints[ENDPOINT]["s3_template"]

    snapshot_key = build_s3_key(
        endpoints["fixtures"]["s3_template"],
        league=league_id,
        season=season,
        target_date=target_date,
    )
    finished = select_finished_fixtures(
        read_json_from_s3(bucket, snapshot_key),
        endpoints[ENDPOINT]["finished_statuses"],
    )
    stored = list_s3_keys(bucket, prefix=template.partition("{")[0])
    pending = [
        fixture_id
        for fixture_id in finished
        if build_s3_key(template, fixture=fixture_id) not in stored
    ]
    logger.info(
        f"Snapshot has {len(finished)} finished matches, {len(pending)} not stored yet."
    )
    return pending


def store_match(
    config: dict, item: dict, response: dict, params: dict, target_date: str
) -> None:
    """Writes the details of one match as its own object, replacing any older one.

    Raises:
        ValueError: If the response lacks a detail section altogether.
    """
    fixture_id = item["fixture"]["id"]
    absent = [section for section in DETAIL_SECTIONS if section not in item]
    if absent:
        raise ValueError(f"Fixture {fixture_id} came without sections: {absent}.")
    # Coverage differs between leagues, so an empty section is not an error.
    empty = [section for section in DETAIL_SECTIONS if not item[section]]
    if empty:
        logger.warning(f"Fixture {fixture_id} has empty sections: {empty}.")

    envelope = DataEnvelope(
        _metadata=Metadata(endpoint=ENDPOINT, params=params, target_date=target_date),
        payload={**response, "results": 1, "response": [item]},
    )
    upload_to_s3(
        envelope.model_dump(by_alias=True, mode="json"),
        config["aws_s3_landing_bucket"],
        build_s3_key(
            config["api"]["endpoints"][ENDPOINT]["s3_template"], fixture=fixture_id
        ),
    )


def run_match_details_pipeline(
    config: dict,
    target_date: str,
    league_id: int | None = None,
    season: int | None = None,
    fixture_id: int | None = None,
    max_fixtures: int | None = None,
) -> None:
    """
    Downloads match details to S3, one object per match.

    Takes finished matches of the league season from the fixtures snapshot of
    target_date and skips those already stored, so an interrupted or limited run
    continues where it stopped.

    Args:
        config (dict): Application configuration with secrets.
        target_date (str): Date of the fixtures snapshot to read.
        league_id (int | None): League of the snapshot.
        season (int | None): Season of the snapshot.
        fixture_id (int | None): Downloads this match only, even if it is stored.
        max_fixtures (int | None): Matches per run, overrides the configuration.

    Raises:
        ValueError: If filters or settings are invalid, or the API omits a
            requested match or a detail section.
    """
    endpoint_config = config["api"]["endpoints"][ENDPOINT]
    limits = config["api"]["limits"]
    batch_size = endpoint_config["batch_size"]
    if max_fixtures is None:
        max_fixtures = endpoint_config["max_fixtures_per_run"]
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ValueError(f"batch_size must be from 1 to {MAX_BATCH_SIZE}.")
    if max_fixtures < 1:
        raise ValueError("The number of fixtures per run must be positive.")

    if fixture_id is not None:
        selected = [fixture_id]
    elif league_id is None or season is None:
        raise ValueError(f"'{ENDPOINT}' needs a fixture, or a league and a season.")
    else:
        pending = find_pending_fixtures(config, league_id, season, target_date)
        selected = pending[:max_fixtures]

    for start in range(0, len(selected), batch_size):
        if start:
            time.sleep(limits["delay_seconds"])
        batch = selected[start : start + batch_size]
        params = (
            {"id": batch[0]}
            if batch_size == 1
            else {"ids": "-".join(str(item) for item in batch)}
        )
        response = fetch_data(
            url=config["api"]["base_url"] + endpoint_config["path"],
            headers={config["api"]["headers"]["key_name"]: config["api_football_key"]},
            timeout=(limits["timeout_connect"], limits["timeout_read"]),
            query_params=params,
            delay_seconds=limits["delay_seconds"],
            max_retries=limits["max_retries"],
            retry_delay_seconds=limits["retry_delay_seconds"],
        )

        returned = {item["fixture"]["id"]: item for item in response["response"]}
        for requested in batch:
            if requested in returned:
                store_match(config, returned[requested], response, params, target_date)
        if missing := [item for item in batch if item not in returned]:
            raise ValueError(f"The API returned no data for fixtures: {missing}.")

    logger.info(f"Stored details of {len(selected)} matches.")
