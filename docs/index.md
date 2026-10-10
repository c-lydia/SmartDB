# SmartDB documentation

```{image} _static/smartdb-logo.svg
:alt: SmartDB shield and wordmark
:width: 160px
:align: center
```

Build, configure and understand the current **SmartDB v2 bench system**: an ESP32-S3
main board with SCT-013 AC current monitoring, MLX90640 thermal sensing, relay protection
and RGB–thermal fusion, plus a separate ESP32-CAM for visible images.

## Backend and frontend integration

The [Firebase API and team handoff](system/index.md) now cover accounts, device credentials,
durable telemetry/history, alerts, queued commands and fused-image previews. Run
`sh system.sh` from the repository root for local emulators and an optional developer
console. **The frontend team owns the user dashboard**; this console is only for API
development. Read the [current architecture](system/architecture.md) for responsibilities
and the [PCB downloads](hardware/index.md#files-and-previews) for the permanent v2 CAD.

## Start with the setup menu

Open `esp_idf/smartdb_fusion` in VS Code and choose
**Terminal → Run Task → SmartDB: Setup**. Or run `./setup.sh` from that folder.

1. Enter Wi-Fi settings with menu **1**.
2. Connect the camera's USB programmer directly to the computer and choose **2**.
3. Connect the main board through J4 USB-C and choose **3**.
4. Use **4** for protection limits, **5** for status, and **8** for the fused-image viewer.

The menu can build and flash the correct firmware for each board. After that initial
update, connection settings persist on the boards and can be changed over USB without
reflashing. J6 supplies camera power only. Physical re-arm is still required to close
the relay, and real camera alignment remains an installation calibration step.

Read the [complete setup and configuration guide](firmware/index.md) for wiring,
saved settings, troubleshooting and calibration. The [Postman guide](api/index.md)
covers the HTTP interfaces; Postman is optional for setup. Browse the
[firmware code guide](code/index.md), [local HTTP API](api/http.md),
[USB setup protocol](api/usb.md) and [telemetry reference](api/telemetry.md) for implementation
details. [ByteLab](related/bytelab.md) documents the related desktop development workspace.

## Implementation status

| Available now | Still requires validation or implementation |
|---|---|
| S3 and ESP32-CAM firmware, USB setup menu, saved Wi-Fi/configuration | Physical board provisioning and sensor/relay behavior |
| Local AC current/thermal protection, physical re-arm, event history | Actual current accuracy, cutoff timing and component ratings |
| Registered thermal overlay and native-sample region statistics | Measured camera alignment; trained cloud AI models |
| Firebase HTTP API, telemetry/history, in-app alerts, command acknowledgements and stored fused preview | Live Firebase deployment, external notifications and production operations |
| Optional local developer console and documented frontend API | User dashboard implementation by the frontend team |

Firmware builds and host tests pass. Hardware operation has not been validated in this
design session. The current scope is isolated low-voltage AC monitoring up to the 1 A
bench limit; the board's logic supply remains regulated 5 V DC. This is not a mains-rated
protection design. The architecture page separates the implemented bench system from
the wider production requirements.

```{toctree}
:maxdepth: 2
:caption: SmartDB v2

system/index
system/architecture
system/console
firmware/index
hardware/index
hardware/board
api/index
backend/index
architecture_full_v1.1
project
```

```{toctree}
:maxdepth: 2
:caption: Code and API reference

code/index
code/interfaces
code/protocol-source
api/http
api/usb
api/telemetry
```

```{toctree}
:maxdepth: 2
:caption: Related projects

related/projects
related/bytelab
```

```{toctree}
:maxdepth: 1
:caption: Development reference

reference/embedded_system/platformio/configuration
reference/embedded_system/esp_idf/workflow
reference/embedded_system/esp_idf/blink_led
reference/embedded_system/esp_idf/blink_led_api
reference/language_ref/preprocessor
reference/language_ref/pointer_and_smart_pointer
reference/yolo_architecture/yolov26
reference/embedded_system/jetson_nano_pipeline/nvidia_sdk_manager/jetson_nano_config
firmware/legacy-camera
README
```
