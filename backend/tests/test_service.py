from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

from smartdb_ingestion.codec import encode_cbor
from smartdb_ingestion.service import IngestionService
from smartdb_ingestion.storage import MessageStore


def message(sequence: int = 1) -> dict:
    return {
        "device_id": "db-001",
        "schema_version": "1.0.0",
        "message_id": str(uuid4()),
        "sequence_number": sequence,
        "boot_id": str(uuid4()),
        "occurred_at": "2026-08-04T10:00:00Z",
        "time_quality": "synced",
        "sent_at": "2026-08-04T10:00:01Z",
        "payload": {
            "sample_period_ms": 100,
            "samples": [{
                "sample_offset_ms": 0, "current_rms_a": 4.2,
                "max_temperature_c": 41.3, "relay_state": "closed",
            }],
        },
    }


def service(_tmp_path, window: int = 64) -> IngestionService:
    return IngestionService(MessageStore(window), 1024, 120)


def test_accepts_and_deduplicates_exact_message(tmp_path: Path) -> None:
    svc = service(tmp_path)
    value = message()
    first = svc.ingest("telemetry", encode_cbor(value), "db-001")
    second = svc.ingest("telemetry", encode_cbor(value), "db-001")
    assert (first.code, first.body["status"]) == ("2.04", "accepted")
    assert (second.code, second.body["status"]) == ("2.04", "duplicate")


def test_rejects_identity_mismatch_and_invalid_schema(tmp_path: Path) -> None:
    svc = service(tmp_path)
    value = message()
    assert svc.ingest("telemetry", encode_cbor(value), "another-device").code == "4.01"
    value["schema_version"] = "1"
    assert svc.ingest("telemetry", encode_cbor(value), "db-001").code == "4.00"


def test_reused_id_or_sequence_with_different_content_conflicts(tmp_path: Path) -> None:
    svc = service(tmp_path)
    original = message()
    assert svc.ingest("telemetry", encode_cbor(original), "db-001").code == "2.04"
    changed = deepcopy(original)
    changed["payload"]["samples"][0]["current_rms_a"] = 9.1
    assert svc.ingest("telemetry", encode_cbor(changed), "db-001").code == "4.09"
    other_id = deepcopy(original)
    other_id["message_id"] = str(uuid4())
    assert svc.ingest("telemetry", encode_cbor(other_id), "db-001").code == "4.09"


def test_replay_window_allows_reordering_and_rejects_old_unknown(tmp_path: Path) -> None:
    svc = service(tmp_path, window=64)
    for sequence in (100, 36):
        result = svc.ingest("telemetry", encode_cbor(message(sequence)), "db-001")
        assert result.code == ("2.04" if sequence == 100 else "4.01")
    assert svc.ingest("telemetry", encode_cbor(message(99)), "db-001").code == "2.04"


def test_supports_full_uint64_range(tmp_path: Path) -> None:
    svc = service(tmp_path)
    result = svc.ingest("telemetry", encode_cbor(message(2**64 - 1)), "db-001")
    assert result.code == "2.04"


def test_rejects_oversized_and_malformed_payloads(tmp_path: Path) -> None:
    svc = service(tmp_path)
    assert svc.ingest("telemetry", b"x" * 1025, "db-001").code == "4.00"
    assert svc.ingest("telemetry", b"not-cbor", "db-001").code == "4.00"
