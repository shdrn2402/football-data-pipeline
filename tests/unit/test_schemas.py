from datetime import UTC

import pytest
from pydantic import ValidationError

from schemas import DataEnvelope, Metadata


def test_metadata_defaults():
    meta = Metadata(endpoint="fixtures", params={"season": 2024})

    assert meta.source == "api-football"
    assert meta.endpoint == "fixtures"
    assert meta.params == {"season": 2024}
    assert meta.ingested_at.tzinfo == UTC


def test_data_envelope_serialization():
    meta = Metadata(endpoint="leagues", params={})
    # В ingest.py используется инициализация через алиас _metadata
    envelope = DataEnvelope(_metadata=meta, payload={"data": "test"})

    dumped = envelope.model_dump(by_alias=True, mode="json")

    assert "_metadata" in dumped
    assert "metadata" not in dumped
    assert dumped["payload"] == {"data": "test"}
    assert "ingested_at" in dumped["_metadata"]


def test_metadata_validation_error_on_missing_endpoint():
    with pytest.raises(ValidationError):
        Metadata(params={"season": 2024})
