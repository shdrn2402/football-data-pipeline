from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Metadata(BaseModel):
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = "api-football"
    endpoint: str
    params: dict[str, Any]


class DataEnvelope(BaseModel):
    metadata: Metadata = Field(alias="_metadata")
    payload: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)
