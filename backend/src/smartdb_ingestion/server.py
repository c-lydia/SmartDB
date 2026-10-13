from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path

import aiocoap
import aiocoap.resource as resource

from .codec import CBOR_CONTENT_FORMAT, CodecError, decode_cbor, encode_cbor
from .service import IngestionService
from .settings import Settings
from .storage import MessageStore
from .transport import IdentityAdapter, require_dtls_runtime

LOG = logging.getLogger(__name__)
KINDS = {
    "telemetry": "telemetry",
    "critical": "critical",
    "health": "health",
    "config_ack": "config_ack",
}

COAP_CODES = {
    "2.04": aiocoap.CHANGED,
    "2.05": aiocoap.CONTENT,
    "2.03": aiocoap.VALID,
    "4.00": aiocoap.BAD_REQUEST,
    "4.01": aiocoap.UNAUTHORIZED,
    "4.09": aiocoap.CONFLICT,
    "4.15": aiocoap.UNSUPPORTED_CONTENT_FORMAT,
    "4.29": aiocoap.TOO_MANY_REQUESTS,
}


class IngestResource(resource.Resource):
    def __init__(self, service: IngestionService, identities: IdentityAdapter, kind: str) -> None:
        super().__init__()
        self.service = service
        self.identities = identities
        self.kind = kind

    async def render_post(self, request: aiocoap.Message) -> aiocoap.Message:
        if request.opt.content_format != CBOR_CONTENT_FORMAT:
            return self._response("4.15", {"error": "Content-Format must be application/cbor"})
        # Bound the body before decoding, including the preliminary identity claim.
        # The service still owns schema validation and authenticated identity matching.
        try:
            decoded = decode_cbor(request.payload, self.service.max_payload_bytes)
            if not isinstance(decoded, dict):
                raise CodecError("CBOR envelope must be a map")
            claim = decoded.get("device_id")
            if not isinstance(claim, str) or not claim:
                raise CodecError("device_id must be a nonempty string")
        except CodecError:
            return self._response("4.00", {"error": "invalid message"})

        try:
            identity = self.identities.identity_for(request, claim).device_id
        except Exception as exc:
            LOG.warning("identity rejection: %s", exc)
            return self._response("4.01", {"error": "authentication failed"})

        result = self.service.ingest(self.kind, request.payload, identity)
        return self._response(result.code, result.body)

    @staticmethod
    def _response(code: str, body: dict) -> aiocoap.Message:
        return aiocoap.Message(
            code=COAP_CODES[code],
            payload=encode_cbor(body),
            content_format=CBOR_CONTENT_FORMAT,
        )


class ConfigResource(resource.Resource):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    async def render_get(self, request: aiocoap.Message) -> aiocoap.Message:
        try:
            payload = self.path.read_bytes()
        except OSError:
            return aiocoap.Message(code=aiocoap.NOT_FOUND)

        etag = hashlib.sha256(payload).digest()[:8]

        if etag in request.opt.etags:
            return aiocoap.Message(code=aiocoap.VALID, etag=etag)

        return aiocoap.Message(
            code=aiocoap.CONTENT,
            payload=payload,
            content_format=CBOR_CONTENT_FORMAT,
            etag=etag,
        )


async def run(settings: Settings) -> None:
    if settings.transport_mode == "secure":
        require_dtls_runtime()

    store = MessageStore(settings.replay_window_size)
    service = IngestionService(store, settings.max_payload_bytes, settings.rate_limit_per_minute)
    identities = IdentityAdapter(settings.transport_mode == "insecure-dev")
    site = resource.Site()
    site.add_resource(["v1", "telemetry"], IngestResource(service, identities, "telemetry"))
    site.add_resource(["v1", "events", "critical"], IngestResource(service, identities, "critical"))
    site.add_resource(["v1", "health"], IngestResource(service, identities, "health"))
    site.add_resource(["v1", "config", "ack"], IngestResource(service, identities, "config_ack"))
    site.add_resource(["v1", "config"], ConfigResource(settings.config_path))
    context = await aiocoap.Context.create_server_context(site, bind=(settings.host, settings.port))
    LOG.info("SmartDB ingestion listening on coap://%s:%d", settings.host, settings.port)

    try:
        await asyncio.get_running_loop().create_future()
    finally:
        await context.shutdown()
        store.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(run(Settings()))


if __name__ == "__main__":
    main()
