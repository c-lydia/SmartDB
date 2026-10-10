# Firmware code guide

The firmware lives in `esp_idf/smartdb_fusion`. PlatformIO builds the source files into
one image per board: `smartdb_s3` for the main board and `esp32cam` for the separate
AI Thinker camera. `smartdb_s3_demo` produces synthetic fusion output and keeps the
relay off. Use the [setup menu](../firmware/index.md) to configure, build and flash.

## Build structure

`platformio.ini` selects the board and SDK defaults. `main/CMakeLists.txt` selects the
application sources for the ESP-IDF target; shared components are compiled and linked
automatically. You do not build or flash each C file separately.

```{literalinclude} ../../esp_idf/smartdb_fusion/platformio.ini
:language: ini
:linenos:
```

```{literalinclude} ../../esp_idf/smartdb_fusion/main/CMakeLists.txt
:language: cmake
:linenos:
```

## Where to change behavior

Paths below are relative to `esp_idf/smartdb_fusion`; links download the current source.

| Source | Responsibility |
|---|---|
| [main/app_s3.c](../../esp_idf/smartdb_fusion/main/app_s3.c) | S3 startup, camera fetch, fusion worker, viewer, status and telemetry snapshot |
| [main/app_camera.c](../../esp_idf/smartdb_fusion/main/app_camera.c) | AI Thinker pin map, camera startup and fresh JPEG endpoint |
| [main/system_control.c](../../esp_idf/smartdb_fusion/main/system_control.c) | Current/thermal acquisition tasks, relay GPIO, physical re-arm, persistent events and control configuration |
| [main/sensor_bus.c](../../esp_idf/smartdb_fusion/main/sensor_bus.c), [main/thermal_sensor.c](../../esp_idf/smartdb_fusion/main/thermal_sensor.c) | Shared I²C bus and MLX90640 acquisition |
| [components/fusion_core/fusion_core.c](../../esp_idf/smartdb_fusion/components/fusion_core/fusion_core.c) | Registration, frame pairing, bicubic display, native-pixel region measurements and BMP encoding |
| [components/fusion_core/protection.c](../../esp_idf/smartdb_fusion/components/fusion_core/protection.c) | Portable protection state machine and DC-removed RMS calculation |
| [main/network.c](../../esp_idf/smartdb_fusion/main/network.c) | Wi-Fi station, reconnection, cached IP and local HTTP authentication |
| [main/device_settings.c](../../esp_idf/smartdb_fusion/main/device_settings.c) | Connection settings validation, NVS storage and redacted readback |
| [main/serial_setup.c](../../esp_idf/smartdb_fusion/main/serial_setup.c) | USB setup request/response protocol on both boards |
| [main/telemetry.c](../../esp_idf/smartdb_fusion/main/telemetry.c) | HTTPS publisher, bounded queue, preview upload, command delivery and acknowledgements |
| [main/cloud_control.c](../../esp_idf/smartdb_fusion/main/cloud_control.c) | Persistent command retry handling, telemetry interval and shared configuration application |
| [tools/setup.py](../../esp_idf/smartdb_fusion/tools/setup.py) | Interactive configuration, board selection, build/flash and USB provisioning |
| [tools/calibrate.py](../../esp_idf/smartdb_fusion/tools/calibrate.py) | Fits the installation's RGB-to-thermal homography |
| [config/calibration.h](../../esp_idf/smartdb_fusion/config/calibration.h) | Alignment, display scale and measurement regions |
| [config/project_config.h](../../esp_idf/smartdb_fusion/config/project_config.h) | Build defaults and acquisition/fusion settings |

The Melexis driver is under `components/mlx90640`; its
[upstream record](../../esp_idf/smartdb_fusion/components/mlx90640/UPSTREAM)
documents the pinned source and local changes.

## Startup and task boundaries

The S3 calls `system_start()` first, opening the relay and starting local protection.
It then loads connection settings, starts USB setup, allocates fusion buffers and starts
the network and fusion tasks. Waiting for Wi-Fi does not block local sensing/protection.
The HTTP server and optional telemetry publisher start after the network is ready.

| Work | Scheduling / data boundary |
|---|---|
| Protection | Core 1, priority 15, 10 ms loop; reads validated sensor snapshots and drives relay state |
| Current acquisition | Core 1, priority 12; 200 ms RMS windows from ADS1115 |
| Thermal acquisition | Core 1, priority 8; completes and validates MLX90640 frames |
| Fusion | Core 0, priority 4; publishes image and region metadata under a mutex |
| Network startup | Core 0, priority 3; starts HTTP and telemetry after connection |
| Event persistence | Separate worker; GPIO cutoff precedes NVS event storage |

These are configured scheduling periods, not measured end-to-end cutoff guarantees.
The current snapshot expires after 500 ms; thermal data expires after 1.5 s. Invalid or
stale sensing trips an armed controller. Boot never automatically arms the relay.
Only the local BOOT hold/release procedure can re-arm after the required healthy interval.
HTTP and USB can open the relay, but cannot arm it.

The camera starts USB setup before camera/network initialization. USB remains the recovery
path when credentials are missing or camera initialization fails; a running camera HTTP
server returns 503 when a capture is unavailable.

## Fusion and measurement

The S3 fetches a fresh 320 × 240 JPEG over Wi-Fi and pairs its complete request/response
interval with the MLX90640 acquisition interval. Their combined time span must fit within
500 ms. Published images expire after 2 s. Calibration is disabled until the installation's
correspondences have been measured and a valid transform has been supplied.

Bicubic interpolation improves the appearance of the thermal overlay. Region statistics
use the original 32 × 24 sensor samples, excluding invalid/corrected samples and ambiguous
boundaries; interpolation does not create additional temperature measurements. There is
no trained object detector or arc detection implementation in this firmware.

## Configuration ownership

| Configuration | Storage and application |
|---|---|
| Wi-Fi, local API token, camera identity/URL, telemetry URL/token | USB setup saves NVS; takes effect after restart |
| Commissioning, current/temperature limits, current scale | HTTP or USB saves a strictly newer version; opens relay and requires local re-arm |
| Camera alignment, region geometry, emissivity, acquisition constants | Source configuration; rebuild the S3 image |

The [USB reference](../api/usb.md) defines complete settings replacements. The
[local HTTP reference](../api/http.md) defines the shared control configuration.
Both transports call the same `system_config_apply()` validation and persistence code.

## Source interfaces and verification

The [C interfaces](interfaces.md) are included directly from the headers at documentation
build time. For request framing and response generation, see the
[protocol implementation listings](protocol-source.md).

From the firmware folder, `sh tools/check.sh` runs portable fusion/protection tests,
MLX failure handling, NVS settings tests and Python calibration/setup/Postman contract tests.
Install `test/requirements.txt` and build a firmware target once to obtain the pinned cJSON
dependency before running the full checks. PlatformIO target builds verify embedded linking;
host tests do not establish physical sensor accuracy, camera timing or relay performance.

ByteLab can edit and inspect these sources; its current SmartDB workflow and integration
limits are documented in [ByteLab](../related/bytelab.md).
