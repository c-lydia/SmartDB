# Telemetry and central API

The S3 implements an optional **HTTPS telemetry publisher**. The receiving
[Firebase API](../system/index.md) is implemented in `cloud/`, with local emulators,
durable telemetry, owner-scoped queries and command delivery. The separate
[Python backend](../backend/index.md) is a CoAP/CBOR gateway. The camera supplies JPEG
snapshots to S3 and does not upload telemetry. The frontend team integrates with this
API; the optional developer console is not the user dashboard.

## Configure delivery

In the [setup menu](../firmware/index.md), enter the complete HTTPS upload URL and its
server-issued bearer token, apply settings to S3 and restart. For the central contract,
the URL has this form:

```text
https://YOUR_API_HOST/api/v1/devices/YOUR_DEVICE_ID/telemetry
```

The URL identifies the server-side device record; the USB MAC identity and installation
ID do not automatically register a device. Leave `telemetry_url` empty to disable uploads.
`telemetry_token` is separate from the local board `api_token`.

Uploads send `Content-Type: application/json` and `Authorization: Bearer <telemetry_token>`.
The publisher verifies the HTTPS certificate through the ESP-IDF certificate bundle,
disables redirects and expects **202 Accepted**.

## Payload

The central `Telemetry` schema and a complete saved request are maintained in
[`postman/specs/smartdb_api/openapi.yaml`](../../postman/specs/smartdb_api/openapi.yaml) and
[`upload_telemetry.request.yaml`](../../postman/collections/smartdb_api/telemetry/upload_telemetry.request.yaml).

| Field | S3 behavior |
|---|---|
| `voltage`, `power` | Null; these measurements are not acquired |
| `current` | Valid AC RMS current in amperes, otherwise null |
| `temperature` | Valid native thermal maximum in °C, otherwise null |
| `timestamp` | UTC timestamp once the clock is valid; otherwise null |
| `time_quality` | `synced` or `unknown` |
| `sample_id` | Random boot identifier plus sample counter; unchanged across retries |
| `uptime_ms` | Monotonic uptime at snapshot time |
| `synthetic` | True for demo firmware |
| `relay_state`, `protection_state`, `protection_reason` | Local controller/output state |
| `config_version`, `commissioned`, `storage_ok` | Configuration and storage status |
| `current_sensor`, `arc_detection_available` | CT description; arc detection is false |
| `events` | Up to 16 recent protection transitions |
| `vision` | Fusion availability, identity, calibration, display scale and native-sample regions |

Fusion fields are nested in `vision` here; they are at the root of local HTTP `/status`.
The [status reference](http.md#read-status) describes region and event fields. Missing
measurements are null, not zero. Render unknown/stale data as unavailable and retain the
`synthetic` distinction. SNTP starts with the network; the current timestamp check treats
a system time at or after 2024-01-01 as valid, rather than providing a precision guarantee.

## Queue, retry and server responsibilities

The collector defaults to every 5 s, configurable to 5–60 s through cloud commands. A RAM queue holds 12 waiting JSON payloads, in addition
to any in-flight payload. When full, it evicts the oldest waiting sample. The uploader
keeps retrying its in-flight payload at 5, 10, 20, 40 and then 60 s intervals until it receives
202. Other status codes, including permanent 4xx errors, currently retry; correct an invalid
URL/token through setup and restart. There is no automatic token refresh.

The implemented server authenticates the device, validates the payload, deduplicates
`sample_id` within that device and returns 202 after Firestore persistence. A lost acknowledgement
can cause the same sample to be sent again. Queue contents are lost at reboot. Recent
events are separately persisted in NVS and included in later snapshots, but an abrupt loss
of power before an event commit can still lose that event.

HTTP upload availability does not control the local relay protection loop. The 202 response
may deliver a command; firmware applies it, persists the result and posts an acknowledgement.
Supported commands are OPEN_RELAY, REQUEST_STATUS, SET_INTERVAL and server-generated
APPLY_CONFIG. Configuration opens the relay, preserves commissioning/current calibration,
and requires physical re-arm. There is no remote close command. See the
[delivery and command contract](../system/index.md#delivery-configuration-and-commands).

After accepted telemetry, the S3 uploads a fresh fused BMP at most once per 30 seconds,
or at the telemetry interval when longer. Only the latest preview is stored. Failed
images are dropped, and the API returns receipt time and synthetic metadata when reading
the image. A stored preview is not live video or a current thermal measurement.

## Other central routes

The [Postman collection guide](index.md#collection-coverage) documents authentication,
users, notifications, device records, configuration, telemetry history, alerts and command
routes under `/api/v1`. These describe the server contract, not extra routes hosted on S3.
The [architecture](../architecture_full_v1.1.md) describes the wider production transport.

The [telemetry source listing](../code/protocol-source.md#https-telemetry-worker) shows the
implemented queue and retry behavior. `main/app_s3.c` constructs each snapshot.
