from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Metadata(BaseModel):
    """
    Metadata envelope for tracking data provenance and API request context.
    """

    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of when the data was extracted.",
    )
    source: str = Field(
        default="api-football",
        description="Identifier of the source system.",
    )
    endpoint: str = Field(description="The specific API endpoint called.")
    params: dict[str, Any] = Field(
        description="Query parameters used for the API request."
    )
    target_date: str = Field(description="Logical execution date in YYYY-MM-DD format.")

    model_config = ConfigDict(extra="forbid")


class DataEnvelope(BaseModel):
    """
    Standardized container for all raw data ingested into the data lake.
    Combines execution metadata with the raw JSON payload.
    """

    metadata: Metadata = Field(
        alias="_metadata",
        description="System metadata, aliased with underscore to match S3 JSON structure.",
    )
    payload: dict[str, Any] = Field(
        description="Raw JSON response from the source API."
    )

    model_config = ConfigDict(populate_by_name=True)
