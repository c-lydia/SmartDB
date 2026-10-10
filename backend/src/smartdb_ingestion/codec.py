from __future__ import annotations

from io import BytesIO
from typing import Any

import cbor2

CBOR_CONTENT_FORMAT = 60

class CodecError(ValueError):
    pass

def decode_cbor(payload: bytes, max_bytes: int) -> Any:
    if len(payload) > max_bytes:
        raise CodecError(f"payload exceeds {max_bytes} bytes")
    try:
        stream = BytesIO(payload)
        decoded = cbor2.CBORDecoder(stream).decode()
        if stream.read(1):
            raise CodecError("trailing bytes after CBOR envelope")
        return decoded
    except Exception as exc:
        raise CodecError("malformed CBOR") from exc

def encode_cbor(value: Any) -> bytes:
    return cbor2.dumps(value, canonical=True)
