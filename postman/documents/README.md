# SmartDB Postman Collection Guide

The `smartdb_api` collection exercises the user- and administrator-facing SmartDB HTTP API.
The authoritative product and device architecture is
[`docs/architecture_full_v1.1.md`](../../docs/architecture_full_v1.1.md); the machine-readable
HTTP contract is [`postman/specs/smartdb_api/openapi.yaml`](../specs/smartdb_api/openapi.yaml).
Collection requests and examples must remain aligned with both.

## Protocol boundary

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
| `base_url` | `http://localhost:8000/api/v1` | Every HTTP request |
| `token` | Access token returned by login | Protected requests |
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

## Recommended workflow

1. Start an HTTP API implementation that conforms to `openapi.yaml`.
2. Send `authentication/login` and copy `access_token` into the local `token` value.
3. Register or list devices and set `device_id` to a record the user may access.
4. Exercise configuration, telemetry queries, alerts, notifications, and commands.
5. Use the saved examples to compare methods, routes, status codes, and response shapes.
6. Clear tokens and one-time device credentials when testing is complete.

The collection does not prove that an API implementation exists or that authorization is
correct. Automated contract and permission tests remain required.

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
