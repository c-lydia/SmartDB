# SmartDB Device Ingestion Gateway

This service implements the device-facing CoAP/CBOR contract in
[`docs/architecture_full_v1.1.md`](../docs/architecture_full_v1.1.md). It validates,
authenticates, deduplicates, and replay-checks messages before forwarding them. It is
deliberately separate from the user-facing HTTP API.

## Status and security boundary

The validation path can run locally in `insecure-dev` mode. Secure
mode fails closed because aiocoap does not expose a verified server-side DTLS-PSK hook in
this build. **Never expose insecure-dev mode to a network.** Local relay protection remains
independent of this service, as required by the system safety invariant.

## Quick start

Python 3.11 or newer is required.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
SMARTDB_TRANSPORT_MODE=insecure-dev smartdb-ingestion
```

The default listener is UDP `127.0.0.1:5687` (loopback). An explicit `SMARTDB_HOST`
override can expose the listener; use `insecure-dev` only for local testing. To run the tests:

```bash
pytest
```

For requirements, see the [architecture source](../docs/architecture_full_v1.1.md).
The [Postman guide](../postman/documents/README.md) describes the separate HTTP contract;
this gateway does not implement a FastAPI server.

## Resources

| Resource | Method | Payload/result |
|---|---:|---|
| `/v1/telemetry` | POST | Telemetry envelope; development acknowledgement |
| `/v1/events/critical` | POST | Critical-event envelope; development acknowledgement |
| `/v1/health` | POST | Health envelope; development acknowledgement |
| `/v1/config/ack` | POST | Config acknowledgement envelope |
| `/v1/config` | GET | Config file bytes with ETag validation; signature verification is not implemented |

POST requests must use CoAP Content-Format 60 (`application/cbor`). A success response is
also CBOR and includes `message_id`, `sequence_number`, `status`, and `server_time`.
Exact retries return the original success status; reused identifiers with different content
return `4.09`; unknown sequences below the replay window return `4.01`.
Malformed, oversized, non-map, or trailing-data CBOR returns `4.00`. The size limit
is applied before decoding the identity claim. Identity authentication failures return
`4.01`; malformed envelopes are not treated as authentication failures.

## Configuration

Settings use the `SMARTDB_` prefix and may also be placed in `backend/.env`.

| Variable | Default | Purpose |
|---|---|---|
| `SMARTDB_HOST` | `127.0.0.1` | Bind address; defaults to loopback |
| `SMARTDB_PORT` | `5687` | UDP port |
| `SMARTDB_TRANSPORT_MODE` | `secure` | `secure` or local-only `insecure-dev` |
| `SMARTDB_DTLS_PSK_FILE` | unset | JSON PSK file required by secure mode |
| `SMARTDB_MAX_PAYLOAD_BYTES` | `1024` | Maximum CBOR body size |
| `SMARTDB_REPLAY_WINDOW_SIZE` | `1024` | Allowed out-of-order sequence window |
| `SMARTDB_RATE_LIMIT_PER_MINUTE` | `120` | Per-identity request limit |
| `SMARTDB_CONFIG_PATH` | `./config/device-config.cbor` | Signed config served to devices |

The PSK file format is `{"db-001":"<hex-encoded secret>"}`. Use independently generated
256-bit secrets (at least 32 bytes / 64 hex characters), keep the file outside source
control, and restrict filesystem permissions. The PSK loader rejects shorter keys and
invalid identity maps; this does not enable the pending DTLS integration.

## Development state model

Replay and duplicate metadata is held only in gateway memory and is bounded by the replay
window. It is lost on restart. Consequently, the current acknowledgement is suitable only
for development: production must atomically validate and store messages in Firebase or
another external durable service before returning the contract's durable `2.04` response.
The development response omits `accepted_through_sequence`: it cannot prove a contiguous
durable checkpoint and must not authorize bulk removal of queued device messages.

## Production checklist

- Integrate and verify a server-side DTLS 1.2 PSK terminator; leave fail-closed behavior in place.
- Store PSKs in a secrets manager/HSM boundary and implement rotation/revocation.
- Implement a Firebase/managed-database adapter that atomically preserves both uniqueness
  constraints and replay state before acknowledging a message.
- Add sustained/burst and critical-event-specific token buckets per the normative architecture.
- Export redacted metrics and security alerts for replay, conflicts, authentication, and latency.
- Generate and sign the canonical CBOR device config offline; never serve an unsigned config.
- Validate MTU, power-loss recovery, load, and end-to-end device retry behavior before pilot use.
