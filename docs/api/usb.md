# USB setup protocol

The [setup menu](../firmware/index.md) uses this protocol to provision either board without
rebuilding firmware. It also supports manual inspection through
[ByteLab's Protocol page](../related/bytelab.md). Connect each board directly to the computer:
S3 through J4 USB-C, camera through its USB programmer base. J6 is power only.

## Framing

Use the USB-to-UART port at **115200 baud**, 8 data bits, no parity, 1 stop bit. Each request
is one line: the literal prefix `SMARTDB `, a JSON object, then LF. CRLF also works because
the firmware ignores CR. The limit is 4095 bytes before LF, including the prefix. An
overlong line is discarded through the next LF; unrelated console lines are ignored.

```text
SMARTDB {"id":"inspect-1","op":"info"}
```

`id` is a string of at most 32 bytes. Responses use the same prefix and echo the ID.
Clients must ignore normal boot/log output and responses with other IDs. A response has
`ok: true`, or `ok: false` and an ESP-IDF error name such as `ESP_ERR_INVALID_ARG`.
There is no HTTP bearer authentication on this physical USB interface.

## Operations

| `op` | Boards | Request `data` | Response / effect |
|---|---|---|---|
| `info` | Both | Omitted | `protocol: 1`, `board`, MAC `device_id`, `uptime_ms`, `ip`, redacted active `settings`; S3 also includes control status |
| `save_settings` | Both | Complete eight-field settings object | Persists settings; `restart_required: true`; S3 opens relay on the attempt |
| `restart` | Both | Omitted | Acknowledges, then restarts after about 200 ms; S3 opens relay |
| `read_control` | S3 | Omitted | Applied five-field configuration in `config` |
| `write_control` | S3 | Complete control configuration | Same validation/persistence as HTTP `PUT /config`; relay opens on accepted update |
| `open_relay` | S3 | Omitted | Opens relay without clearing a latched trip |

`board` is `smartdb_s3` or `esp32cam`. `ip` is empty while offline. USB `info` includes
control measurements on S3, but no fusion image/region metadata. Use HTTP `/status` for
that metadata. Camera requests for S3-only operations return `ESP_ERR_INVALID_ARG`.

## Read and update control limits

```text
SMARTDB {"id":"limits-1","op":"read_control"}
```

An illustrative response (the actual limits and version depend on the board):

```text
SMARTDB {"id":"limits-1","config":{"version":1,"commissioned":false,"current_limit_a":0.8,"temperature_limit_c":60,"current_scale_a_per_v":111.1111},"ok":true}
```

`write_control` places the complete configuration in `data`; use a strictly newer version.
The [HTTP reference](http.md#replace-control-configuration) lists the limits. Conflicting
versions or concurrent updates return `ESP_ERR_INVALID_STATE`. The TUI handles version
increments for you. Neither interface has an arm operation.

## Connection settings

`save_settings` requires all eight fields, including empty telemetry fields when disabled.
It replaces the whole record; omitted secrets are not retained. Lengths below are UTF-8
bytes, excluding the terminating NUL used internally.

| Field | Limit and meaning |
|---|---|
| `wifi_ssid` | 1–32 bytes |
| `wifi_password` | 8–63 bytes; WPA2 network password |
| `api_token` | 24–96 printable ASCII bytes without spaces; shared S3/camera HTTP token |
| `camera_url` | Up to 191 bytes; `http://` camera capture URL, e.g. `http://192.168.1.50/capture` |
| `camera_id` | 1–63 bytes; expected camera identity |
| `installation_id` | 1–63 bytes; installation identifier |
| `telemetry_url` | Empty to disable uploads, or up to 255 bytes beginning `https://` |
| `telemetry_token` | Up to 700 bytes; nonempty printable ASCII without spaces when telemetry is enabled |

All fields must be strings without ASCII control characters. URLs reject spaces,
non-ASCII characters, user-info (`@`) and fragments (`#`). The TUI additionally checks
URL structure and ports. The camera uses the same settings record format; the TUI clears
the cloud telemetry URL/token when provisioning it.

On successful save:

```text
SMARTDB {"id":"settings-1","restart_required":true,"ok":true}
```

Send `restart`, reconnect and request `info` to confirm the active settings and IP.
Readback hides `wifi_password`, `api_token` and `telemetry_token`, replacing their values
with `wifi_password_set`, `api_token_set` and `telemetry_token_set` booleans. Active settings
remain unchanged until restart, even if the save succeeded.

Use the TUI for entering credentials; manual serial entry can leave credentials in a
monitor's history or export. Close ByteLab/other serial monitors before the setup menu or
flasher accesses the same port. The [source listing](../code/protocol-source.md#usb-dispatcher)
shows dispatch, error handling and framing.
