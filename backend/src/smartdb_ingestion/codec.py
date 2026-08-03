from __future__ import annotations

from typing import Any

import cbor2

CBOR_CONTENT_FORMAT = 60

class CodecError(ValueError):
    pass

def decode_cbor(payload: bytes, max_bytes: int) -> Any:
    if len(payload) > max_bytes:
        raise CodecError(f"payload exceeds {max_bytes} bytes")
    try:
        return cbor2.loads(payload)
    except Exception as exc:
        raise CodecError("malformed CBOR") from exc

def encode_cbor(value: Any) -> bytes:
    return cbor2.dumps(value, canonical=True)
