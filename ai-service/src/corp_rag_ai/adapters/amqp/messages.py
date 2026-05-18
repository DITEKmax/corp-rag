from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

CORRELATION_ID_HEADER = "x-correlation-id"
EVENT_TYPE_HEADER = "x-event-type"
EVENT_VERSION_HEADER = "x-event-version"


@dataclass(frozen=True, slots=True)
class EventMetadata:
    event_id: UUID
    event_type: str
    event_version: str
    occurred_at: datetime
    correlation_id: UUID
    source_service: str

    def to_json(self) -> dict[str, str]:
        return {
            "eventId": str(self.event_id),
            "eventType": self.event_type,
            "eventVersion": self.event_version,
            "occurredAt": _isoformat_utc(self.occurred_at),
            "correlationId": str(self.correlation_id),
            "sourceService": self.source_service,
        }


@dataclass(frozen=True, slots=True)
class InboundEvent:
    metadata: EventMetadata
    payload: dict[str, Any]
    headers: Mapping[str, Any]


def decode_inbound_event(body: bytes, headers: Mapping[str, Any]) -> InboundEvent:
    raw = json.loads(body.decode("utf-8"))
    metadata = raw.get("metadata")
    payload = raw.get("payload")
    if not isinstance(metadata, dict):
        raise ValueError("event metadata must be an object")
    if not isinstance(payload, dict):
        raise ValueError("event payload must be an object")
    return InboundEvent(metadata=_parse_metadata(metadata), payload=payload, headers=headers)


def build_envelope(
    *,
    event_type: str,
    payload: Mapping[str, Any],
    correlation_id: UUID,
    event_version: str,
    source_service: str,
    occurred_at: datetime | None = None,
    event_id: UUID | None = None,
) -> dict[str, Any]:
    metadata = EventMetadata(
        event_id=event_id or uuid4(),
        event_type=event_type,
        event_version=event_version,
        occurred_at=occurred_at or datetime.now(UTC),
        correlation_id=correlation_id,
        source_service=source_service,
    )
    return {"metadata": metadata.to_json(), "payload": dict(payload)}


def resolve_correlation_id(headers: Mapping[str, Any], metadata: EventMetadata | Mapping[str, Any] | None) -> UUID:
    header_value = _parse_uuid(headers.get(CORRELATION_ID_HEADER))
    if header_value is not None:
        return header_value
    if isinstance(metadata, EventMetadata):
        return metadata.correlation_id
    if isinstance(metadata, Mapping):
        metadata_value = _parse_uuid(metadata.get("correlationId"))
        if metadata_value is not None:
            return metadata_value
    return uuid4()


def encode_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, default=_json_default, separators=(",", ":")).encode("utf-8")


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return _isoformat_utc(value)
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Type {type(value)} is not JSON serializable")


def _parse_metadata(value: Mapping[str, Any]) -> EventMetadata:
    return EventMetadata(
        event_id=UUID(str(value["eventId"])),
        event_type=str(value["eventType"]),
        event_version=str(value["eventVersion"]),
        occurred_at=_parse_datetime(str(value["occurredAt"])),
        correlation_id=UUID(str(value["correlationId"])),
        source_service=str(value["sourceService"]),
    )


def _parse_datetime(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _parse_uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
