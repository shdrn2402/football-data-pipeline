import json
import logging
import os
import string
import time
from pathlib import Path

import boto3
import botocore.exceptions
import requests
import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config(config_path: str | Path, env_path: str | Path) -> dict:
    """Loads YAML configuration and injects environment variables.

    Args:
        config_path (str): Path to the config.yaml file.
        env_path (str): Path to the .env file.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the YAML file is malformed.

    Returns:
        dict: Parsed configuration data.
    """
    # Silently ignores if .env is missing (expected in Docker/cloud)
    load_dotenv(env_path)
    config_path = Path(config_path)

    try:
        config = yaml.safe_load(config_path.read_text())
        config["api_football_key"] = os.environ["API_FOOTBALL_KEY"]
        config["aws_s3_landing_bucket"] = os.environ["AWS_S3_LANDING_BUCKET_NAME"]
    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        raise
    except KeyError as e:
        logger.error(f"Missing environment variable: {e}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Error parsing YAML file: {e}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied when accessing the configuration file: {e}")
        raise

    return config


def fetch_data(
    url: str,
    headers: dict,
    timeout: tuple,
    query_params: dict | None = None,
    delay_seconds: int = 0,
) -> dict:
    """Executes GET requests to the API, automatically handling pagination
    and rate limiting across multiple pages.

    Args:
        url (str): The endpoint URL.
        headers (dict): Request headers containing authentication tokens.
        timeout (tuple): Connection and read timeouts (connect, read).
        query_params (dict | None, optional): Query string parameters. Defaults to None.
        delay_seconds (int, optional): Sleep time between paginated requests to respect rate limits. Defaults to 0.

    Raises:
        requests.exceptions.HTTPError: If the HTTP request returns an unsuccessful status code.
        requests.exceptions.RequestException: For underlying network issues.
        ValueError: If the API response contains business logic errors despite a 200 OK status.

    Returns:
        dict: Consolidated JSON payload containing all items in the 'response' array/object.
    """
    params = (query_params or {}).copy()

    all_records: list = []
    current_page = 1
    total_pages = 1
    consolidated_payload: dict = {}

    while current_page <= total_pages:
        if current_page > 1:
            params["page"] = current_page
        logger.info(f"Fetching page {current_page}/{total_pages} from {url}...")

        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=timeout
            )
            response.raise_for_status()
            data = response.json()

            if data.get("errors"):
                errors = data["errors"]
                # Gracefully handle API plan limitations (e.g., Free tier max pages)
                if isinstance(errors, dict) and "plan" in errors:
                    logger.warning(
                        f"API plan limitation reached on page {current_page}. "
                        f"Stopping pagination. Reason: {errors['plan']}"
                    )
                    break
                # Raise exception for any other API errors
                raise ValueError(f"API returned errors: {errors}")

            # Initialize the payload structure and determine total pages on the first request
            if current_page == 1:
                consolidated_payload = data.copy()
                total_pages = data.get("paging", {}).get("total", 1)

            records = data.get("response", [])

            # Handle both list (e.g., players, fixtures) and dict (e.g., team statistics) response formats
            if isinstance(records, list):
                all_records.extend(records)
            else:
                all_records.append(records)

            logger.info(
                f"Page {current_page} fetched. Items in current batch: "
                f"{len(records) if isinstance(records, list) else 1}"
            )

            # Apply rate limiting delay if there are more pages to fetch
            if current_page < total_pages and delay_seconds > 0:
                time.sleep(delay_seconds)

            current_page += 1

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error on page {current_page} for {url}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error on page {current_page} for {url}: {e}")
            raise

    # Update metadata in the final consolidated object
    consolidated_payload["response"] = all_records
    consolidated_payload["results"] = len(all_records)
    if "paging" in consolidated_payload:
        consolidated_payload["paging"]["current"] = total_pages

    logger.info(
        f"Pagination completed: Total {len(all_records)} records collected across {total_pages} pages."
    )
    return consolidated_payload


def build_s3_key(template_string: str, **kwargs) -> str:
    """Constructs an S3 key dynamically, appending extra parameters as folders."""
    try:
        template_keys = {
            t[1] for t in string.Formatter().parse(template_string) if t[1] is not None
        }

        base_path = template_string.format(**kwargs)

        extra_params = []
        for key, value in kwargs.items():
            if key not in template_keys and key != "target_date":
                extra_params.append(f"{key}={value}")

        if extra_params:
            s3_key = f"{base_path}/{'/'.join(sorted(extra_params))}/data.json"
        else:
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
