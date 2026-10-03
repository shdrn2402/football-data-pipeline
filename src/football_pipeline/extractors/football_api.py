import logging
import time

import requests

logger = logging.getLogger(__name__)


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
