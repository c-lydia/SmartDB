# SmartDB Postman Collection Guide

The `smartdb_api` collection exercises the user- and administrator-facing SmartDB HTTP API.
The authoritative product and device architecture is
[`docs/architecture_full_v1.1.md`](../../docs/architecture_full_v1.1.md); the machine-readable
HTTP contract is [`postman/specs/smartdb_api/openapi.yaml`](../specs/smartdb_api/openapi.yaml).
Collection requests and examples must remain aligned with both.

The website also provides detailed references for the
[local HTTP API](../../docs/api/http.md), [USB setup protocol](../../docs/api/usb.md),
[telemetry delivery](../../docs/api/telemetry.md) and [firmware code](../../docs/code/index.md).

## Protocol boundary

### Implemented v2 bench firmware

The [PlatformIO firmware](../../esp_idf/smartdb_fusion/README.md) explicitly uses the
diagnostic HTTP contract for optional bench telemetry. In the setup menu, enter the full
**HTTPS** upload URL and the server's telemetry bearer token, then apply settings to S3.
The [Firebase API](../../cloud/README.md) implements these routes. Start it locally with
`sh system.sh`; live Firebase deployment is a separate installation step. The existing
CoAP gateway remains separate. The firmware expects 202 and retries the same `sample_id`;
the API deduplicates that identifier within the device. Its 12-entry RAM telemetry queue
evicts older waiting samples during long outages and does not survive reboot.

For normal setup, use the firmware's `./setup.sh` menu to enter the endpoint/token and
configure Wi-Fi over USB. Settings persist in NVS without rebuilding; `SMARTDB_TELEMETRY_URL`
and `SMARTDB_TELEMETRY_TOKEN` are optional developer fallbacks. The menu also adjusts protection limits using the same
validation/persistence logic as `PUT /config`, with automatic version increments. Postman
remains available for API inspection; it is no longer required to configure the boards.

The upload example now reflects real v2 capability: null voltage/power, AC RMS current,
native thermal maximum, relay/protection status, recent events and `vision` metadata.
Unavailable measurements and unsynchronized UTC timestamps are null. Unsupported or stale
regions have null temperature statistics. `synthetic` distinguishes demo output; do not
interpret synthetic readings as installation evidence. The schema still accepts the
earlier five-field numeric telemetry shape.

Local requests in `smartdb_api/firmware` use **`firmware_token`**, separately from the
server's `token`. Set `firmware_url` to the S3 address and `camera_url` to the camera address.
The [local firmware OpenAPI contract](../specs/smartdb_firmware/openapi.yaml) covers:

| Request | Target | Behavior |
|---|---|---|
| `GET /status` | S3 | Fusion status plus local measurements/protection |
| `GET /config` | S3 | Applied bench configuration |
| `PUT /config` | S3 | Newer complete configuration; opens relay, needs physical re-arm |
| `POST /relay/open` | S3 | Opens relay; cannot clear a trip or re-arm |
| `GET /fused.bmp` | S3 | Fresh fused image, or 503 when unavailable |
| `GET /capture` | Camera | Fresh QVGA JPEG with identity/sequence headers |

The saved configuration example deliberately leaves `commissioned: false`. Increase the
version above the applied version; only commission after the sensor/installation settings
are ready. Local error responses are plain text, separate from the central API's `Error`
schema. Image requests include unavailable-frame examples; successful responses are binary.
Local HTTP bearer tokens are unencrypted, so use an isolated bench network. There is no
remote close/re-arm request. Runtime BOOT hold/release is the physical re-arm mechanism.

The remainder of this guide describes the production API boundary and central collection.

Postman sends JSON over HTTP or HTTPS. It does **not** exercise the ESP32 ingestion protocol.

| Client | Protocol | Security | Interface |
|---|---|---|---|
| Mobile/admin tools | HTTP JSON | HTTPS/TLS plus bearer token | `/api/v1/...` |
| ESP32 production device | CoAP CBOR over UDP | DTLS 1.2 with per-device PSK | `/v1/...`, UDP 5687 |

Do not change collection URLs to `coaps://`: Postman does not act as the DTLS CoAP test
client. Test the device contract with ESP32 integration firmware or a DTLS-capable CoAP
harness. The HTTP diagnostic telemetry, heartbeat, and sync endpoints are for authorized
development and operations only; they are not substitutes for production CoAP/DTLS.

## Import and environment setup

Open the repository as a Postman local workspace or import the collection, environment, and
OpenAPI file. Select `smartdb_dev`, then check these variables:

| Variable | Example | Used by |
|---|---|---|
| `base_url` | `http://127.0.0.1:5000/api/v1` | Central HTTP API requests |
| `token` | Access token returned by login | Protected central API requests |
| `device_token` | Provisioned one-time device key | Device-only command acknowledgement |
| `firmware_url` | `http://192.168.1.51` | Local S3 requests in `firmware/` |
| `camera_url` | `http://192.168.1.50` | Camera `/capture` request |
| `firmware_token` | Shared token created by the setup menu | Local S3 and camera requests; different from the server token |
| `device_id` | `ESP32_001` | Device, config, telemetry, and command routes |
| `alert_id` | `1` | Alert resolution |
| `notification_id` | `10` | Notification read state |
| `command_id` | `1001` | Command acknowledgement |
| `from`, `to` | RFC 3339 UTC timestamps | Telemetry history range |
| `limit` | `100` | Telemetry history page size |

The checked-in `token` is intentionally empty. Never commit real credentials, refresh
tokens, API keys, DTLS PSKs, user passwords, or production hostnames. Use Postman's local
current-value/secret facilities for sensitive values.

For protected requests, configure collection-level authorization as Bearer Token with
`{{token}}`. Login and refresh are public token endpoints and should override inherited
authorization when necessary. Production `base_url` must use `https://` with a valid,
trusted certificate.

The setup tool does not write secrets into these checked-in Postman files. Copy the actual
board addresses from the menu. For local requests, use the shared token in your private
Postman environment; menu **8 — Open fused-image viewer** can display it explicitly for
copying after the S3 has been set up. Local requests already use `{{firmware_token}}` in
their Authorization header.

## Recommended workflow

1. Run `sh system.sh` from the repository root; the launcher prints emulator login credentials.
2. Send `authentication/login` and copy `access_token` into the local `token` value.
3. Register or list devices and set `device_id` to a record the user may access.
4. Exercise configuration, telemetry queries, alerts, notifications, and commands.
5. Use the saved examples to compare methods, routes, status codes, and response shapes.
6. Clear tokens and one-time device credentials when testing is complete.

The implemented API has emulator-backed permission and persistence tests (`npm test`).
The [team handoff](../../cloud/README.md#frontend-handoff) covers token rotation, CORS,
null/stale data, asynchronous commands and image response headers. The frontend team owns
the user dashboard. Configuration `sampling_rate` means a 5–60 second **upload interval**,
not the electrical/thermal acquisition rate. Desired limits apply only after acknowledgement.

`GET /devices/{device_id}/commands` returns acknowledgements; a device credential receives
only its oldest pending command. `POST /devices/{device_id}/credential/rotate` replaces a
lost key. `GET /devices/{device_id}/fusion/frame` returns the most recent stored BMP with
receipt/synthetic metadata. Device-only upload and command acknowledgement requests must
use the provisioned **device key**, not the user login token.

## Collection coverage

### Authentication

| Request | Method and route | Expected success |
|---|---|---|
| Login | `POST /auth/login` | `200`, access/refresh token pair |
| Refresh token | `POST /auth/refresh` | `200`, rotated token pair |
| Logout | `POST /auth/logout` | `204`, refresh token revoked |

Refresh tokens should rotate on use. Logout must be idempotent from the user's perspective,
and authentication failures must not reveal whether an account exists.

### Users and notifications

| Request | Method and route | Expected success |
|---|---|---|
| List users | `GET /users` | `200`; administrator only |
| Current user | `GET /users/me` | `200` |
| Update profile | `PATCH /users/me` | `200` |
| Notification settings | `GET /users/me/notification-settings` | `200` |
| List notifications | `GET /notifications` | `200` |
| Mark read | `PATCH /notifications/{notification_id}/read` | `200` |

Every object lookup must be scoped to the authenticated tenant/user. A valid identifier must
not allow access to another household's device, alert, notification, telemetry, or command.

### Devices and configuration

| Request | Method and route | Expected success |
|---|---|---|
| Register device record | `POST /devices` | `201` |
| Provision credential | `POST /device/register` | `201`; restricted, one-time secret |
| List/get device | `GET /devices`, `GET /devices/{device_id}` | `200` |
| Device status | `GET /devices/{device_id}/status` | `200` |
| Read configuration | `GET /devices/{device_id}/config` | `200` |
| Replace configuration | `PUT /devices/{device_id}/config` | `200` |
| Diagnostic heartbeat | `POST /devices/{device_id}/heartbeat` | `202` |
| Diagnostic sync | `POST /devices/{device_id}/sync` | `200` |

Credential provisioning must be separately authorized and audited. A device key may be
returned once during provisioning but must never appear in list/get responses or logs.
Desired configuration changes do not prove device application; production uses the signed
CBOR config and explicit device acknowledgement described in the architecture.

### Telemetry, alerts, and commands

| Request | Method and route | Expected success |
|---|---|---|
| Latest telemetry | `GET /devices/{device_id}/telemetry/latest` | `200` |
| Telemetry history | `GET /devices/{device_id}/telemetry` | `200` |
| Diagnostic upload | `POST /devices/{device_id}/telemetry` | `202` |
| List/create alerts | `GET /alerts`, `POST /alerts` | `200`, `201` |
| Resolve alert | `PUT /alerts/{alert_id}/resolve` | `200` |
| Send command | `POST /devices/{device_id}/commands` | `202` |
| Acknowledge command | `POST /devices/{device_id}/commands/{command_id}/ack` | `204` |

User-issued commands must obey the safety policy. In Release 1, remote re-energizing after a
critical cutoff is prohibited without the required physical reset/admin procedure. HTTP
commands never replace the ESP32's independent local threshold and cutoff path.

## Status and error conventions

| Status | Meaning |
|---|---|
| `200 OK` | Successful read/update with a response body |
| `201 Created` | Resource synchronously created |
| `202 Accepted` | Work queued for asynchronous processing |
| `204 No Content` | Action recorded with no response body |
| `400 Bad Request` | Invalid JSON, field, query, or state transition |
| `401 Unauthorized` | Authentication missing, invalid, or expired |
| `403 Forbidden` | Authenticated principal lacks permission |
| `404 Not Found` | Resource absent or concealed by tenant scoping |
| `409 Conflict` | Duplicate resource or version/state conflict |
| `422 Unprocessable Content` | Structurally valid JSON violates domain validation |
| `429 Too Many Requests` | Rate limit exceeded; honor retry metadata |

Errors use the OpenAPI `Error` schema: `code`, human-readable `message`, and optional
`request_id`. Responses must not expose stack traces, secrets, database details, or whether
an inaccessible cross-tenant resource exists.

## Maintaining the collection

For every change:

- update `openapi.yaml` first and treat it as the HTTP contract;
- update the corresponding request URL, method, body, and environment variables;
- add or update at least one linked success example;
- keep GET requests body-free and put response data in examples;
- use plural resource routes consistently except the explicitly retained provisioning route;
- ensure example methods, routes, bodies, and statuses match their requests and OpenAPI;
- add negative contract tests for validation, authentication, authorization, and conflicts;
- never place device DTLS material in Postman files; and
- record architecture/security changes in `architecture_full_v1.1.md`.

Before merging, parse every YAML file, validate OpenAPI 3.1, scan for unresolved `{{...}}`
variables, and run collection tests against a disposable environment. Production collection
runs must use a test tenant and non-safety-critical hardware.
