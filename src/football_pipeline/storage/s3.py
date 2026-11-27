import json
import logging

import boto3
import botocore.exceptions

logger = logging.getLogger(__name__)

# Query parameters that narrow a response, mapped to their S3 partition names.
# "id" selects a player on /players; elsewhere it is part of the template.
FILTER_PARTITIONS = {
    "league": "league_id",
    "season": "season",
    "team": "team_id",
    "player": "player_id",
    "id": "player_id",
    "fixture": "fixture_id",
}


def add_filter_partitions(template_string: str, query_params: dict) -> str:
    """Extends a key template with the filters it does not already contain.

    A filtered response is a subset, so it must not share a key with the full one.
    The partitions go before the date partition, or at the end if there is none.
    """
    partitions = "".join(
        f"/{partition}={query_params[param]}"
        for param, partition in FILTER_PARTITIONS.items()
        if param in query_params and f"{{{param}}}" not in template_string
    )
    base, separator, date_part = template_string.partition("/date=")
    return f"{base}{partitions}{separator}{date_part}"


def build_s3_key(template_string: str, **kwargs) -> str:
    """Constructs an S3 key strictly based on the provided template string.

    Raises:
        KeyError: If a placeholder of the template has no value.
    """
    values = {key: value for key, value in kwargs.items() if value is not None}
    try:
        base_path = template_string.format(**values)
        s3_key = f"{base_path}/data.json"
    except KeyError as e:
        logger.error(f"Missing placeholder for S3 key construction: {e}")
        raise
    except Exception as e:
        logger.error(f"Error constructing S3 key from template: {e}")
        raise

    return s3_key


def upload_to_s3(data: str | dict, bucket: str, s3_key: str) -> None:
    """Uploads a dictionary as a JSON object to an AWS S3 bucket.

    Args:
        data (str | dict): The payload to serialize and upload.
        bucket (str): The name of the target S3 bucket.
        s3_key (str): The destination key (path) in the S3 bucket.

    Raises:
        botocore.exceptions.ClientError: If the AWS S3 put_object operation fails.
        TypeError: If the data object is not JSON serializable.
    """
    s3 = boto3.resource("s3")
    body = json.dumps(data, ensure_ascii=False, indent=4)
    try:
        s3.Bucket(bucket).put_object(Key=s3_key, Body=body)
    except botocore.exceptions.ClientError as e:
        logger.error(
            f"Failed to upload data to S3 bucket '{bucket}' at '{s3_key}': {e}"
        )
        raise
    except botocore.exceptions.ParamValidationError as e:
        logger.error(
            f"Parameter validation error during S3 upload to bucket '{bucket}' at '{s3_key}': {e}"
        )
        raise


def read_json_from_s3(bucket: str, s3_key: str) -> dict:
    """Reads a JSON object from an AWS S3 bucket.

    Raises:
        botocore.exceptions.ClientError: If the object cannot be read.
    """
    try:
        response = boto3.client("s3").get_object(Bucket=bucket, Key=s3_key)
    except botocore.exceptions.ClientError as e:
        logger.error(f"Failed to read S3 bucket '{bucket}' at '{s3_key}': {e}")
        raise
    return json.loads(response["Body"].read())


def list_s3_keys(bucket: str, prefix: str) -> set[str]:
    """Returns all object keys under a prefix.

    Raises:
        botocore.exceptions.ClientError: If listing is not allowed or fails.
    """
    pages = (
        boto3.client("s3")
        .get_paginator("list_objects_v2")
        .paginate(Bucket=bucket, Prefix=prefix)
    )
    try:
        return {item["Key"] for page in pages for item in page.get("Contents", [])}
    except botocore.exceptions.ClientError as e:
        logger.error(f"Failed to list S3 bucket '{bucket}' at '{prefix}': {e}")
        raise
