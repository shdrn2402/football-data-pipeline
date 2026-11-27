import logging
import time

import requests

logger = logging.getLogger(__name__)


def is_daily_quota_exhausted(response: requests.Response) -> bool:
    """Tells whether retrying today is pointless."""
    return response.headers.get("x-ratelimit-requests-remaining") == "0"


def request_page(
    url: str,
    headers: dict,
    params: dict,
    timeout: tuple,
    max_retries: int,
    retry_delay_seconds: int,
) -> dict:
    """Requests one page, retrying temporary failures with exponential backoff.

    Network errors, HTTP 429 and 5xx, and the per-minute limit reported in the
    response body are temporary, unless the daily quota is exhausted.
    """
    for attempt in range(max_retries + 1):
        is_last_attempt = attempt == max_retries
        try:
            response = requests.get(
                url, headers=headers, params=params, timeout=timeout
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if is_last_attempt:
                raise
            reason = str(e)
        else:
            can_retry = not is_last_attempt and not is_daily_quota_exhausted(response)
            if response.status_code == 429 or response.status_code >= 500:
                if not can_retry:
                    response.raise_for_status()
                reason = f"HTTP {response.status_code}"
            else:
                response.raise_for_status()
                data = response.json()
                errors = data.get("errors")
                is_rate_limited = isinstance(errors, dict) and "rateLimit" in errors
                if not (is_rate_limited and can_retry):
                    return data
                reason = errors["rateLimit"]

        wait_seconds = retry_delay_seconds * 2**attempt
        logger.warning(
            f"Temporary failure: {reason}. Retry {attempt + 1}/{max_retries} "
            f"in {wait_seconds} s."
        )
        time.sleep(wait_seconds)


def fetch_data(
    url: str,
    headers: dict,
    timeout: tuple,
    query_params: dict | None = None,
    delay_seconds: float = 0,
    max_retries: int = 0,
    retry_delay_seconds: int = 0,
) -> dict:
    """Executes GET requests to the API, automatically handling pagination
    and rate limiting across multiple pages.

    Args:
        url (str): The endpoint URL.
        headers (dict): Request headers containing authentication tokens.
        timeout (tuple): Connection and read timeouts (connect, read).
        query_params (dict | None, optional): Query string parameters. Defaults to None.
        delay_seconds (float, optional): Sleep time between paginated requests to respect rate limits. Defaults to 0.
        max_retries (int, optional): Retries per page for temporary failures. Defaults to 0.
        retry_delay_seconds (int, optional): Wait before the first retry, doubled on each next one. Defaults to 0.

    Raises:
        requests.exceptions.HTTPError: If the HTTP request returns an unsuccessful status code.
        requests.exceptions.RequestException: For underlying network issues.
        ValueError: If any page contains API errors, including plan limitations,
            despite a 200 OK status.

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
            data = request_page(
                url, headers, params, timeout, max_retries, retry_delay_seconds
            )

            # Plan limitations arrive here too (HTTP 200, empty response). They
            # must fail the run: a partial result would be stored as a complete one.
            if data.get("errors"):
                raise ValueError(
                    f"API returned errors on page {current_page}: {data['errors']}"
                )

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
