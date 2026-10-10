from __future__ import annotations

import asyncio
import json
from unittest.mock import Mock

import aiocoap
import pytest

from smartdb_ingestion.codec import CBOR_CONTENT_FORMAT, encode_cbor
from smartdb_ingestion.server import IngestResource
from smartdb_ingestion.service import IngestionService
from smartdb_ingestion.settings import Settings
from smartdb_ingestion.storage import MessageStore
from smartdb_ingestion.transport import IdentityAdapter, TransportConfigurationError, load_psks
from test_service import message


def resource(identities=None):
    return IngestResource(
        IngestionService(MessageStore(64), 1024, 120),
        identities if identities is not None else IdentityAdapter(insecure_dev=True),
        "telemetry",
    )


def post(endpoint, payload, content_format=CBOR_CONTENT_FORMAT):
    request = aiocoap.Message(payload=payload, content_format=content_format)
    return asyncio.run(endpoint.render_post(request))


@pytest.mark.parametrize("payload", [
    b"\xff", encode_cbor([]), encode_cbor(None), encode_cbor({}),
    encode_cbor({"device_id": []}), encode_cbor({"device_id": ""}),
    encode_cbor(message()) + b"\x00",
])
def test_invalid_envelopes_are_bad_requests_before_authentication(payload):
    identities = Mock()
    response = post(resource(identities), payload)
    assert response.code == aiocoap.BAD_REQUEST
    identities.identity_for.assert_not_called()


def test_oversized_body_never_reaches_decoder(monkeypatch):
    decoder = Mock(side_effect=AssertionError("must not decode oversized input"))
    monkeypatch.setattr("smartdb_ingestion.codec.cbor2.CBORDecoder", decoder)
    assert post(resource(), b"x" * 1025).code == aiocoap.BAD_REQUEST
    decoder.assert_not_called()


def test_coap_resource_accepts_valid_message_and_rejects_wrong_content_type():
    payload = encode_cbor(message())
    endpoint = resource()
    assert post(endpoint, payload).code == aiocoap.CHANGED
    assert post(endpoint, payload, content_format=0).code == aiocoap.UNSUPPORTED_CONTENT_FORMAT


def test_authentication_failure_is_unauthorized():
    identities = Mock()
    identities.identity_for.side_effect = TransportConfigurationError("not authenticated")
    assert post(resource(identities), encode_cbor(message())).code == aiocoap.UNAUTHORIZED


@pytest.mark.parametrize("raw", [
    {}, [], {"": "ab" * 32}, {"db-001": "ab" * 16},
    {"db-001": "ab" * 31}, {"db-001": "not-hex"}, {"db-001": 123},
])
def test_rejects_invalid_or_short_psks(tmp_path, raw):
    path = tmp_path / "keys.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(TransportConfigurationError):
        load_psks(path)


def test_accepts_256_bit_and_longer_psks(tmp_path):
    path = tmp_path / "keys.json"
    path.write_text(json.dumps({"db-001": "ab" * 32, "db-002": "cd" * 48}))
    assert load_psks(path) == {"db-001": bytes.fromhex("ab" * 32), "db-002": bytes.fromhex("cd" * 48)}


def test_local_development_defaults_to_loopback(monkeypatch):
    monkeypatch.delenv("SMARTDB_HOST", raising=False)
    assert Settings(_env_file=None, transport_mode="insecure-dev").host == "127.0.0.1"
