# SmartDB v2 system firmware

One **PlatformIO project using ESP-IDF**, with two firmware targets:

| Target | Board | Responsibilities |
|---|---|---|
| `smartdb_s3` | SmartDB v2 ESP32-S3-WROOM-1-N16R8 | AC current, thermal sensing, local cutoff, configuration/event storage, RGB–thermal fusion, HTTP status and HTTPS telemetry |
| `esp32cam` | Separate AI Thinker ESP32-CAM + USB programmer base | Fresh QVGA JPEG capture over Wi-Fi |
| `smartdb_s3_demo` | Same S3, optional demonstration | Synthetic fusion, relay always disabled; not another required board |

PlatformIO compiles and links the source files automatically. **Flash one image per board,
not one file at a time.** J6 supplies the external camera's USB power; image data uses Wi-Fi.
The MLX90640 connects to the S3 over I²C. The existing older SD-card camera experiment is
separate from this project.

This implements the **isolated low-voltage AC monitoring bench scope, up to 1 A**.
The PCB logic supply remains DC; do not apply AC to its DC power input. Relay contact
voltage/current ratings and the selected load must be checked against the actual relay BOM.
This is not a mains protection firmware or a validated protective device.

## Easy setup — one terminal menu

Open **`esp_idf/smartdb_fusion` itself** in VS Code with PlatformIO installed. Choose
**Terminal → Run Task → SmartDB: Setup**, or launch the menu once:

```sh
./setup.sh
```

The launcher uses PlatformIO's Python and pySerial; no separate TUI package is needed.
It presents a numbered menu, so normal setup does not require editing headers or entering
build/flash commands:

For setup, connect the camera's programmer base **directly to the computer** with a USB
data cable; connect the main board through **J4 USB-C**. J6 on SmartDB supplies camera power
only and cannot carry setup commands or program the camera. Move the camera's USB cable
to J6 for normal operation after programming; do not connect two USB power sources to its
single programmer port. Neither board needs Wi-Fi to accept USB setup commands.

1. **Wi-Fi and connection settings:** enter the 2.4 GHz WPA2 network name/password,
   camera/installation names and optional telemetry endpoint. Password entry is hidden.
   A shared API token is generated for the camera and S3 automatically.
2. **Set up ESP32-CAM:** connect the camera's USB programmer base and select the detected
   port. If the board has older/no setup firmware, the menu offers to build and flash it.
   It then saves settings, restarts, checks Wi-Fi and remembers the camera IP.
3. **Set up SmartDB main board:** connect the S3 board and follow the same process.
   The camera address from step 2 is supplied automatically.
4. **Change protection limits:** read current settings, enter limits/calibration and choose
   whether to mark the installation commissioned. The version increments automatically,
   the board saves the update, and the relay remains open until physical re-arm.

The same menu reads board status, opens the relay, builds/updates either firmware, and opens
the fused-image viewer. It verifies the board type before applying settings. Serial monitors
must be closed because the setup tool needs exclusive access to the port.

**Wi-Fi, API token, camera URL/ID, installation ID and telemetry settings now live in NVS
on the boards. Later changes need USB setup and a restart, not a rebuild/reflash.** USB setup
works before Wi-Fi is configured and while the router is unreachable. An unconfigured camera
no longer resets repeatedly; it waits for setup. Incorrect saved settings can be replaced over
USB. Each board needs the setup-enabled firmware once before this workflow is available.

The local `.setup.json` profile remembers shared settings and device addresses, is git-ignored,
and is written with owner-only permissions on POSIX. It contains secrets in plaintext; it is
not encrypted. Firmware status responses omit passwords/tokens. Physical USB access is the
authorization boundary for provisioning; the network API still requires its bearer token.
Saving connection settings on the S3 opens the relay before storage/restart. There is no
USB or network command to energize/re-arm it.

If Wi-Fi does not connect within the menu's check window, saved settings remain on the board
and USB remains usable. Correct the settings and apply again. Reserve the camera's DHCP IP
in the router; if it changes, set up the camera again and apply its new address to the S3.
Network changes are applied to each board separately, not broadcast wirelessly.

`config/local_config.h` remains an optional developer fallback when no saved NVS settings
exist. Saved connection settings take precedence over those compile-time defaults. Thermal
emissivity/buzzer selection and measured image calibration remain build-time settings.
S3 sensing/protection continue independently of Wi-Fi and of the setup menu.

### What each menu item does

| Choice | Action | When it takes effect |
|---|---|---|
| 1 — Wi-Fi and connection settings | Edit the computer's saved setup profile | Apply to each board with 2 or 3 |
| 2 — Set up ESP32-CAM | Provision camera; offer initial flash if setup firmware is missing | Saves to camera NVS, then restarts and checks Wi-Fi |
| 3 — Set up SmartDB main board | Provision S3 with shared settings and camera address | Saves to S3 NVS, then restarts and checks Wi-Fi |
| 4 — Change protection limits | Read, validate, version and save limits/current calibration | Immediate; opens relay, physical re-arm required |
| 5 — Board status | Read selected board over USB without revealing credentials | Read-only; works offline |
| 6 — Open relay | De-energize S3 relay | Immediate; does not clear a trip |
| 7 — Build / update firmware | Build camera or main-board image; optionally flash | Firmware changes require flashing; saved NVS survives a normal update |
| 8 — Open fused-image viewer | Open the remembered S3 IP in the browser | Requires reachable Wi-Fi; can reveal the shared token on request |
| 0 — Exit | Close the menu | Boards keep running independently |

### Where configuration lives

| Settings | Authoritative storage | How to change |
|---|---|---|
| Wi-Fi, shared API token, camera URL/ID, installation ID | Each board's `connection` NVS namespace | Menu 1, then 2 and/or 3; restart is automatic |
| HTTPS telemetry URL/token | S3 connection NVS; cloud token is not sent to camera | Menu 1, then 3 |
| Trip limits, current scale, commissioning flag/version | S3 `smartdb` NVS namespace | Menu 4 or authenticated Postman `PUT /config` |
| Copy of connection settings and remembered ports/IPs | Computer's ignored `.setup.json` | Menu 1; this file alone does not change either board |
| Optional compile-time connection defaults | Ignored `config/local_config.h` | Developer fallback only; existing NVS settings take precedence |
| Thermal emissivity/reflection assumptions, buzzer type | `config/local_config.h` / project defaults | Rebuild and flash S3 |
| RGB–thermal registration and component regions | `config/calibration.h` | Generate from measured calibration, rebuild and flash S3 |

The setup menu does not measure sensor calibration or camera alignment. Its current-scale
field accepts a calibration value supplied by the operator. Registration remains disabled
until real alignment data is installed; Wi-Fi setup alone does not make fusion ready.

### Setup troubleshooting

| Symptom | Next step |
|---|---|
| VS Code task is missing | Open the firmware project folder, not only the repository root |
| No port appears | Use a USB data cable and the board's programmer connection; J6 cannot pass USB data |
| Port is busy or access is denied | Close other serial monitors; check the operating system's serial-device access permissions |
| No setup response | Release BOOT/IO0 and tap RESET; choose the initial firmware install if it is still running older firmware |
| Wrong board reported | Select the matching menu entry and USB port; do not apply the other board's firmware |
| Wi-Fi settings save but no IP appears | Check 2.4 GHz WPA2 SSID/password, then apply again; USB setup remains available |
| Camera address changed | Set up the camera again, then apply settings to S3; reserve the camera IP in the router |
| Shared token changed | Apply the same profile to both camera and S3 |
| Fused-image request returns 503 | Check `/status` for missing frames, timing, or calibration; USB/Wi-Fi setup does not supply alignment |
| Setup profile was lost | Re-enter credentials and apply a new shared profile to both boards; device status does not return stored secrets |
| Config version conflict | Read settings again; menu 4 normally handles the next version automatically |

The Linux/macOS shell launcher and VS Code task use PlatformIO's Python when installed at
the standard location. On Windows, run `python tools/setup.py` from a PlatformIO terminal
with pySerial available; `setup.sh` needs a compatible shell. Initial build dependency
downloads require internet access. Provisioning and local status do not require a cloud API.

## Manual build and flash (optional)

The menu performs these operations for you; these commands remain available for development:

```sh
pio run -e smartdb_s3
pio run -e esp32cam
```

If `pio` is not on PATH, use the PlatformIO terminal or, on this workstation,
`/home/chheng-lydia/.platformio/penv/bin/pio` in its place. The first build downloads dependencies.
Build targets sequentially: ESP-IDF's shared managed-component lock is target-specific.
The platform and direct component versions are pinned in `platformio.ini` and
`main/idf_component.yml` (ESP-IDF 6.0.1 with espressif32 7.0.1).

Use a data-capable USB cable and list ports:

```sh
pio device list
pio run -e smartdb_s3 -t upload --upload-port /dev/ttyUSB0
pio device monitor -e smartdb_s3 --port /dev/ttyUSB0
```

Then connect the camera's programmer base and use its actual port:

```sh
pio run -e esp32cam -t upload --upload-port /dev/ttyUSB1
pio device monitor -e esp32cam --port /dev/ttyUSB1
```

The port names above are examples; a board may use `/dev/ttyACM0`, another USB number,
or a Windows COM port. Close the serial monitor before uploading. In VS Code, the same
actions are under **PlatformIO → Project Tasks → target → Build / Upload / Monitor**.

If automatic download mode fails, hold BOOT/IO0, tap RESET, start upload, then release
BOOT/IO0 once it connects. After upload, release IO0 and reset to run. The camera base's
buttons and automatic reset circuitry vary by supplier. Holding the S3 BOOT button during
reset selects ROM download mode; runtime re-arm is a different action described below.

PlatformIO uploads the matching bootloader, partition table, and application together.
Generated application images are `.pio/build/smartdb_s3/firmware.bin` and
`.pio/build/esp32cam/firmware.bin`; do not flash either onto the other board. Uploading normally
preserves NVS configuration/trip history; erasing flash removes them. No board has been flashed
as part of this implementation.
The shared `partitions.csv` reserves a 2 MiB application slot on both boards and keeps the
previous NVS/PHY offsets. It does not add OTA support or erase saved configuration.

## Local sensing and protection

The [v2 pin map](../../smart_db_v2/pinmap.csv) is the source for GPIO assignments:

| Function | Connection |
|---|---|
| Relay drive | GPIO4, active high; starts low |
| Buzzer drive | GPIO5 via Q2 |
| RGB status LED | Red GPIO6, green GPIO7, blue GPIO8 |
| I²C | SDA GPIO10, SCL GPIO2, 400 kHz |
| ADS1115 | Address `0x48`, differential AIN0–AIN1 |
| MLX90640 | Address `0x33`, chess acquisition, 8 Hz subpages |
| Local button | BOOT GPIO0, active low |

The SCT-013-000 is **AC-only**, nominal 2000:1, with the board's 18 Ω burden. The ADS1115
uses ±0.256 V range and 860 SPS conversion setting in single-shot mode. Actual sampling is
slower because each conversion is polled over the shared bus. RMS uses a 200 ms sample
window with DC offset removed; nominal scaling is `2000 / 18 = 111.1111 A/V`. Clipping,
I²C failures, insufficient samples and long sample gaps invalidate the window. Accuracy at
sub-amp currents and under simultaneous MLX traffic requires bench characterization and
calibration; a 100 A CT is not intrinsically a precision sub-amp sensor. An unplugged CT can
look like zero current and cannot be diagnosed reliably by this circuit.

Protection runs in a dedicated 10 ms task on core 1, independently of networking/fusion.
It uses native thermal maximum, not bicubic pixels. Current older than 500 ms or thermal
data older than 1.5 s is invalid. An armed unit trips on invalid sensors, overcurrent,
overtemperature, or storage failure. This is windowed monitoring, not instantaneous
short-circuit protection; the 10 ms task period is not an end-to-end cutoff guarantee.
The control task is watched by the 10-second ESP-IDF task watchdog with panic/restart enabled.

Startup is always open. Default configuration is **uncommissioned**, 0.8 A and 60 °C limits.
Use **Change protection limits** in the menu, or read `/config` and PUT all five fields
with a strictly greater `version`; save a calibrated
`current_scale_a_per_v`, limits and `commissioned: true` when the installation is ready.
Configuration changes open the relay and require local re-arm. Current limit is capped at
1 A; temperature range is 20–100 °C. Persistence failures prevent arming.

To re-arm while running: release BOOT first, hold it for at least two seconds, then release.
Both sensors must have remained valid and below recovery thresholds for two seconds
(current below 90% of limit, temperature at least 5 °C below limit). The same gesture opens
an armed relay. A trip remains latched until a qualifying local gesture; **no network endpoint
can close/re-arm the relay**. Reset/power loss never automatically closes it.

LEDs show blue disarmed, green armed and red tripped. Buzzer drive defaults off because
BZ1's active/passive type is not resolved. Set `SMARTDB_ACTIVE_BUZZER=1` only for a verified
active buzzer; it pulses on a trip. Passive buzzer PWM is not implemented.

The last 16 transitions and trip flag persist in NVS through a background writer after
GPIO cutoff. A power loss before that write can lose the newest event, but reboot still
starts open. The event list is a bounded diagnostic history, not an unlimited durable audit log.

## RGB–thermal fusion

The camera serves JPEGs captured after its request arrives. The S3 decodes RGB, pairs the
request interval with the MLX capture interval using its own monotonic clock, and requires
their combined span to fit 500 ms. It does not compare unsynchronized board clocks.
Images expire after two seconds. Stale or missing imagery never blocks local protection.

`config/calibration.h` starts **disabled**. Actual sensor alignment cannot be inferred from
the PCB or a product photograph. For fixed cameras viewing a near-planar target, provide at
least six spread-out corresponding pixel centers in a JSON file:

```json
{
  "version": "panel-1-v1",
  "rgb_size": [320, 240],
  "thermal_size": [32, 24],
  "points": [
    {"rgb": [0, 0], "thermal": [0, 0]},
    {"rgb": [319, 0], "thermal": [31, 0]},
    {"rgb": [0, 239], "thermal": [0, 23]},
    {"rgb": [319, 239], "thermal": [31, 23]},
    {"rgb": [160, 0], "thermal": [15.54858934, 0]},
    {"rgb": [160, 239], "thermal": [15.54858934, 23]}
  ],
  "regions": [{"id": "panel", "rect": [0, 0, 319, 239], "min_samples": 4}]
}
```

These example points are **synthetic**, only showing file format. Replace every point and
region with real correspondences; do not deploy this example as installation calibration.

```sh
python3 tools/calibrate.py measured-points.json config/calibration.h
pio run -e smartdb_s3
```

The tool checks fit residual, geometry and region bounds. Independently validate other
targets afterwards. The runtime does not undistort the JPEG or compensate changing depth;
use a lens/scene where the planar mapping is adequate, or add and validate lens correction
before using it for more demanding geometry. Recalibrate after changing either camera pose,
focus, resolution, mirror/flip setting or target distance.

Bicubic interpolation smooths the display only, with local overshoot clamping. Native
32×24 samples provide region maximum/mean/rise rate. Invalid/factory-bad samples are
excluded. Boundary pixels and ambiguous overlapping region assignments are rejected;
regions with too few native samples are unsupported. Interpolation cannot recover small
hotspots the sensor never resolved. This implementation uses configured component regions;
it does not include a trained YOLO detector or a learned risk score.

For a demonstration without sensor data, build `smartdb_s3_demo`. It marks output synthetic,
uses a synthetic mapping/hotspot, and forces the relay disabled. The browser at the S3's IP
shows the fused image and status after entering the token.

## Firebase integration

The [implemented Firebase API and team handoff](../../cloud/README.md) provide device
credentials, persistent telemetry/history, in-app alerts and command acknowledgements.
The S3 consumes pending commands from accepted telemetry responses and persists the last
result for retry handling. Cloud limits preserve local commissioning and calibration,
open the relay and require physical re-arm. No remote close command exists.

Fresh fused previews upload at most once per 30 seconds, or at the telemetry interval if
longer, to the companion `/fusion/frame` endpoint. Failed preview uploads are dropped.
The backend retains one timestamped BMP per device, separate from numerical native-sample
measurements. The frontend team owns the user dashboard; `dashboard/` is a developer console.

## Postman and telemetry

Use the existing [Postman folder](../../postman/documents/README.md):
`smartdb_api/firmware` contains status, configuration, relay-open, BMP and JPEG requests.
Set `firmware_url`, `camera_url`, and the local `firmware_token` variable. `/status` is available
even with no valid fused image; `/fused.bmp` returns 503 until calibrated fresh fusion exists.

Optional telemetry setup in the menu takes the **full HTTPS** URL matching
`POST /api/v1/devices/{device_id}/telemetry` and a separate telemetry bearer token.
The camera does not receive the cloud telemetry token. The older `SMARTDB_TELEMETRY_URL`
and `SMARTDB_TELEMETRY_TOKEN` defines remain fallback defaults for the S3.
The publisher verifies the server certificate using ESP-IDF's certificate bundle, rejects
redirects, sends every five seconds by default (configurable to 5–60 seconds) and expects HTTP 202. It retries the same `sample_id`
with 5–60 s backoff; a server should deduplicate it. A 12-entry RAM queue discards the oldest
waiting telemetry under prolonged outages. Queued telemetry is lost at reboot; NVS event
history is included in subsequent snapshots. The server implementation lives in `cloud/`;
run its emulators locally or deploy the API to a reachable HTTPS endpoint. Persistent 4xx responses
need credentials/contract correction and hold up the upload queue.

No voltage sensor exists in this pin map: `voltage` and `power` are null. Invalid current or
temperature is null; UTC timestamp is null until the clock is set by SNTP, with monotonic
uptime still supplied. Sensor values and vision readiness are independent. No fabricated
arc-detection score is published. Local camera/control HTTP is bearer-authenticated but
unencrypted; keep it on the isolated bench network. Production CoAP/DTLS, signed configuration,
OTA, cloud AI, application push alerts and production credential provisioning remain separate
architecture work and are not claimed by this bench firmware.

## Verification and source layout

```sh
python3 -m pip install -r test/requirements.txt
pio run -e smartdb_s3 -e smartdb_s3_demo -e esp32cam
sh tools/check.sh
```

Host tests cover protection state transitions, AC RMS conversion, stale data, calibration,
bounded cubic interpolation, ROI ambiguity, BMP encoding, the MLX invalid-auxiliary regression,
Postman request/schema consistency, USB response correlation, setup field validation,
profile file permissions, settings persistence/recovery and credential redaction. Build once
before host tests to fetch the pinned cJSON dependency. Tests produce `test/build/fused-demo.bmp`. Firmware
builds and host tests do not establish real sensor accuracy, frame timing, relay behavior,
thermal calibration, electrical ratings or electromagnetic immunity. No hardware tests have
been performed in this design-only session.

| Files | Purpose |
|---|---|
| `main/app_s3.c`, `main/app_camera.c` | Target-specific application entry points |
| `main/system_control.c`, `main/sensor_bus.c`, `main/thermal_sensor.c` | Board drivers, protection integration, NVS and local control |
| `main/network.c`, `main/telemetry.c` | Wi-Fi, authentication and telemetry |
| `main/device_settings.c`, `main/serial_setup.c` | Persistent connection settings and bounded USB setup protocol |
| `setup.sh`, `tools/setup.py` | Interactive setup/build/flash menu |
| `components/fusion_core/` | Portable fusion, measurement and protection logic |
| `components/mlx90640/` | Pinned Melexis driver with documented auxiliary-error patch |
| `config/` | Installation settings and calibration |
| `tools/`, `test/` | Calibration generation and host verification |

Driver references: [Espressif camera](https://github.com/espressif/esp32-camera/tree/v2.1.6),
[Melexis MLX90640](https://github.com/melexis/mlx90640-library/tree/f6be7ca1d4a55146b705f3d347f84b773b29cc86),
[TI ADS1115 datasheet](https://www.ti.com/lit/ds/symlink/ads1115.pdf).
USB implementation references: [ESP-IDF UART](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/uart.html)
and [pySerial API](https://pyserial.readthedocs.io/en/stable/pyserial_api.html).
