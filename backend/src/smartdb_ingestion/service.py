from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from .codec import CodecError, decode_cbor, encode_cbor
from .models import validate_message
from .rate_limit import SlidingWindowRateLimiter
from .storage import MessageStore

@dataclass(frozen=True)
class IngestResult:
    code: str
    body: dict[str, Any]

class IngestionService:
    def __init__(self, store: MessageStore, max_payload_bytes: int, rate_limit: int) -> None:
        self.store = store
        self.max_payload_bytes = max_payload_bytes
        self.rate_limiter = SlidingWindowRateLimiter(rate_limit)

    def ingest(self, kind: str, raw: bytes, authenticated_device_id: str | None) -> IngestResult:
        if not self.rate_limiter.allow(authenticated_device_id or "unauthenticated"):
            return IngestResult("4.29", {"error": "rate limit exceeded", "retry_after_s": 60})

        try:
            decoded = decode_cbor(raw, self.max_payload_bytes)
            envelope, payload = validate_message(kind, decoded)
        except (CodecError, ValidationError, ValueError, TypeError) as exc:
            return IngestResult("4.00", {"error": "invalid message", "detail": str(exc)})

        del payload

        if authenticated_device_id is None or authenticated_device_id != envelope.device_id:
            return IngestResult("4.01", {"error": "authenticated identity does not match device_id"})

        canonical = encode_cbor(decoded)

        stored = self.store.store(
            envelope.device_id,
            str(envelope.message_id),
            envelope.sequence_number,
            kind,
            hashlib.sha256(canonical).digest(),
            canonical,
        )

        response: dict[str, Any] = {
            "message_id": str(envelope.message_id),
            "sequence_number": envelope.sequence_number,
            "status": stored.status,
            "server_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }

        if stored.accepted_through_sequence is not None:
            response["accepted_through_sequence"] = stored.accepted_through_sequence

        codes = {
            "accepted": "2.04",
            "duplicate": "2.04",
            "conflict": "4.09",
            "replay": "4.01",
        }

        return IngestResult(codes[stored.status], response)
