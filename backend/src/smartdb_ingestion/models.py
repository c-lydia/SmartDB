from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

UInt64 = Annotated[int, Field(ge = 0, le = 2**64 - 1)]
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

class Envelope(BaseModel):
    model_config = ConfigDict(extra = "allow")
    device_id: str = Field(min_length = 1, max_length = 128, pattern = r"^[A-Za-z0-9._-]+$")
    schema_version: str
    message_id: UUID
    sequence_number: UInt64
    boot_id: UUID
    occurred_at: datetime | None
    time_quality: Literal["synced", "estimated", "unknown"]
    sent_at: datetime | None
    payload: dict[str, Any]

    @field_validator("schema_version")
    @classmethod
    def supported_schema(cls, value: str) -> str:
        match = SEMVER_RE.fullmatch(value)

        if match is None:
            raise ValueError("schema_version must be semantic version text")

        major = int(match.group(1))

        if major != 1:
            raise ValueError("unsupported schema major version")

        return value

    @field_validator("occurred_at", "sent_at")
    @classmethod
    def timestamps_have_timezone(cls, value: datetime | None) -> datetime | None:

        if value is None:
            return None

        has_timezone = value.tzinfo is not None and value.utcoffset() is not None

        if not has_timezone:
            raise ValueError("timestamps must include a UTC offset")

        return value.astimezone(timezone.utc)

    @field_validator("message_id", "boot_id")
    @classmethod
    def identifiers_are_uuid4(cls, value: UUID) -> UUID:
        if value.version != 4:
            raise ValueError("message_id and boot_id must be UUIDv4")

        return value

    @field_validator("payload")
    @classmethod
    def payload_is_device_originated(cls, value: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"ai_score", "ai_scores", "ai_classification", "classification", "model_version", "fusion_result"}
        present = forbidden.intersection(value)

        if present:
            raise ValueError(f"device payload contains backend-enrichment fields: {sorted(present)}")

        return value

class TelemetrySample(BaseModel):
    model_config = ConfigDict(extra = "allow")
    sample_offset_ms: int = Field(ge = 0)
    current_rms_a: float = Field(ge = 0)
    max_temperature_c: float
    relay_state: Literal["open", "closed"]

class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra = "allow")
    sample_period_ms: int | None = Field(default = None, ge = 1)
    samples: list[TelemetrySample] = Field(min_length = 1, max_length = 100)

class CriticalPayload(BaseModel):
    model_config = ConfigDict(extra = "allow")
    event_type: str = Field(min_length = 1, max_length = 128)
    severity: Literal["critical"]
    relay_action: str = Field(min_length = 1, max_length = 64)
    trigger: dict[str, Any]
    local_decision_latency_ms: int = Field(ge = 0)

class HealthPayload(BaseModel):
    model_config = ConfigDict(extra = "allow")
    uptime_s: int = Field(ge = 0)
    firmware_version: str
    queue_depth: int = Field(ge = 0)
    queue_capacity: int = Field(ge = 0)
    last_config_version: int = Field(ge = 0)
    reset_reason: str

class ConfigAckPayload(BaseModel):
    model_config = ConfigDict(extra = "allow")
    config_version: int = Field(ge = 0)
    status: Literal["applied", "rejected", "deferred"]
    reason: str | None = Field(default = None, max_length = 512)

PAYLOAD_MODELS = {
    "telemetry": TelemetryPayload,
    "critical": CriticalPayload,
    "health": HealthPayload,
    "config_ack": ConfigAckPayload,
}

def validate_message(kind: str, value: Any) -> tuple[Envelope, BaseModel]:
    if kind not in PAYLOAD_MODELS:
        raise ValueError(f"unsupported message kind: {kind}")

    envelope = Envelope.model_validate(value)
    payload = PAYLOAD_MODELS[kind].model_validate(envelope.payload)
    return envelope, payload
