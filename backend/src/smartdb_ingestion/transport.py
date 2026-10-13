from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class TransportConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class PeerIdentity:
    device_id: str


class IdentityAdapter:
    """Boundary between CoAP resources and transport-authenticated identity."""

    def __init__(self, insecure_dev: bool) -> None:
        self.insecure_dev = insecure_dev

    def identity_for(self, request, claimed_device_id: str) -> PeerIdentity:
        if self.insecure_dev:
            return PeerIdentity(claimed_device_id)

        authenticated = getattr(request.remote, "authenticated_claims", None)

        if not authenticated:
            raise TransportConfigurationError("request has no authenticated DTLS identity")

        identity = authenticated.get("psk_identity")
        if identity is None:
            identity = authenticated.get("identity")

        if isinstance(identity, bytes):
            identity = identity.decode("utf-8")

        if identity != claimed_device_id:
            raise TransportConfigurationError("device_id does not match DTLS PSK identity")

        return PeerIdentity(identity)


def load_psks(path: Path) -> dict[str, bytes]:
    """Load a secret file outside source control: {device_id: hex_psk}."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not raw:
            raise ValueError("PSK file must contain a nonempty identity map")
        psks: dict[str, bytes] = {}

        for identity, value in raw.items():
            if not isinstance(identity, str) or not identity.strip() or not isinstance(value, str):
                raise ValueError("PSK identities and hex keys must be nonempty strings")
            psks[identity] = bytes.fromhex(value)
    except Exception as exc:
        raise TransportConfigurationError(f"cannot load DTLS PSKs from {path}") from exc

    if any(len(value) < 32 for value in psks.values()):
        raise TransportConfigurationError("each DTLS PSK must contain at least 32 bytes (256 bits)")

    return psks


def require_dtls_runtime() -> None:
    """Fail closed until an aiocoap server-side DTLS-PSK backend is installed/configured."""

    try:
        import DTLSSocket  # type: ignore[import-not-found]  # noqa: F401
    except ImportError as exc:
        raise TransportConfigurationError(
            "secure mode requires a platform DTLS backend compatible with aiocoap "
            "(DTLSSocket/tinydtls bindings). Install it and configure server-side PSK "
            "credentials, or use SMARTDB_TRANSPORT_MODE=insecure-dev only for local tests."
        ) from exc
    raise TransportConfigurationError(
        "DTLS bindings are present, but this build does not expose a verified aiocoap "
        "server-side PSK credential hook. Refusing plaintext startup in secure mode."
    )
