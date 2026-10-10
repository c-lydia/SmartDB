# Local HTTP API

The S3 and ESP32-CAM each host an HTTP server at their own Wi-Fi address. Obtain those
addresses through the [setup menu](../firmware/index.md). J6 supplies camera power;
camera requests travel over Wi-Fi.

Except for the S3's HTML viewer shell, requests require
`Authorization: Bearer <api_token>`. Both boards use the shared local token saved during
setup. This is separate from the central telemetry token. Local HTTP does not encrypt
the token; this interface is intended for the isolated bench network.

## Routes and responses

| Board | Method and path | Success | Other defined responses |
|---|---|---|---|
| S3 | `GET /` | 200 HTML viewer shell; data requests still need a token | — |
| S3 | `GET /status` | 200 JSON, fusion and protection status | 401 unauthorized |
| S3 | `GET /config` | 200 JSON, applied control configuration | 401 |
| S3 | `PUT /config` | 200 text, saved and local re-arm required | 400 invalid body/limits, 401, 409 version conflict/update busy, 500 storage failure |
| S3 | `POST /relay/open` | 200 text, relay opening | 401 |
| S3 | `GET /fused.bmp` | 200 binary BMP | 401, 503 unavailable/stale fusion |
| Camera | `GET /capture` | 200 binary JPEG | 401, 503 no fresh frame/camera unavailable |

Error bodies are plain text. Do not parse every response as JSON. The camera does not
implement `/status`; use USB `info` for its settings, identity and IP address.
There is no HTTP close/re-arm endpoint.

## Read status

For example, use Postman's `firmware/get_status` request, or send:

```http
GET /status HTTP/1.1
Host: 192.168.1.51
Authorization: Bearer YOUR_LOCAL_API_TOKEN
```

`/status` places fusion and protection fields together at the JSON root. The outgoing
[telemetry payload](telemetry.md) instead nests fusion metadata under `vision`.

| Fields | Meaning |
|---|---|
| `ready`, `reason`, `synthetic` | Fusion availability, explanation and demo indicator; `ready` does not mean the relay is armed |
| `installation_id`, `camera_id`, `camera_frame_id`, `calibration_version`, `sequence` | Image identity, alignment version and publication sequence |
| `display_min_c`, `display_max_c` | Overlay color scale in °C |
| `regions[]` | Region ID, `supported`, `ambiguous`, `samples`, `boundary_samples`, `max_c`, `mean_c`, `rise_c_per_min` |
| `current`, `temperature` | AC RMS amperes and native thermal maximum °C; null when unavailable/stale |
| `relay_state`, `protection_state`, `protection_reason` | Open/closed output, disarmed/armed/tripped controller and reason |
| `config_version`, `commissioned`, `storage_ok` | Applied configuration and persistent-storage state |
| `current_sensor`, `arc_detection_available` | CT description and false for the unimplemented arc detector |
| `events[]` | Up to 16 transitions: `sequence`, `boot_id`, `uptime_ms`, `state`, `reason`, `current_a`, `temperature_c` |

Unsupported or stale region temperatures are null. `samples` counts native sensor pixels,
not interpolated image pixels. Check `supported` before using a region measurement.
Events use boot-relative time and can include null measurements.

## Replace control configuration

First read `GET /config`, then send all five fields with a version greater than the
applied version. The following body is an example; use a newer version for your board.

```json
{
  "version": 2,
  "commissioned": false,
  "current_limit_a": 0.8,
  "temperature_limit_c": 60,
  "current_scale_a_per_v": 111.1111
}
```

| Field | Validation |
|---|---|
| `version` | Integer 1–4294967295, strictly increasing |
| `commissioned` | Boolean; false keeps the controller uncommissioned |
| `current_limit_a` | Greater than 0 and at most 1 A |
| `temperature_limit_c` | 20–100 °C |
| `current_scale_a_per_v` | 50–200 A/V; actual calibration is installation-specific |

Send `Content-Type: application/json`. The body must be 1–512 bytes with exactly these
five fields. An accepted update opens the relay, commits NVS, invalidates the current
snapshot and resets the healthy re-arm interval. It replies `Saved. Local re-arm required.`
Setting `commissioned` true does not close the relay. On 409, re-read configuration and
resolve the version/update conflict. On 500, storage failed and the relay remains open.

Wi-Fi credentials and endpoint settings use the [USB API](usb.md), not `/config`.

## Open the relay

Send `POST /relay/open` with authentication and no JSON body. The response is
`Relay opening; remote re-arm is not supported.` A latched trip remains latched.
State readback is updated by the protection task; use `/status` to observe it.

## Retrieve images

`GET /fused.bmp` returns a top-down 24-bit 320 × 240 BMP with `X-Fusion-Sequence`.
Match that header to a status sequence when associating metadata with a displayed image;
the two requests are independent and may straddle a new publication. A missing calibration,
unsupported pair or image older than 2 s results in 503.

`GET /capture` on the camera returns a fresh 320 × 240 JPEG, capped at 128 KiB, with:

| Header | Meaning |
|---|---|
| `X-Camera-ID` | Configured camera identity |
| `X-Camera-Boot` | Random boot identifier |
| `X-Camera-Sequence` | Frame sequence |
| `X-Capture-Policy` | `fresh-after-request` |

The camera discards earlier queued frames and tries a bounded number of captures. It
returns 503 if it cannot provide a frame captured after the request. This is a JPEG
snapshot interface, not a continuous video stream.

## Contract and examples

The [local OpenAPI file](../../postman/specs/smartdb_firmware/openapi.yaml) and
[central OpenAPI file](../../postman/specs/smartdb_api/openapi.yaml) live under `postman/specs`.
Keep that directory structure when importing the local spec, because it references the
central fusion schema. Separate website downloads do not preserve relative reference paths.
The [Postman guide](index.md) explains collection variables and saved request examples.
