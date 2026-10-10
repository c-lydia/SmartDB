# PlatformIO setup for SmartDB v2

The current firmware already contains its PlatformIO configuration. Open
[`esp_idf/smartdb_fusion`](../../../../esp_idf/smartdb_fusion/README.md) as the project
folder in VS Code with the PlatformIO IDE extension installed. Do not create a new
ESP Dev Module project for this board; use the checked-in targets and ESP-IDF framework.

## Interactive setup

Choose **Terminal → Run Task → SmartDB: Setup**, or run `./setup.sh` from the firmware
folder. The menu uses PlatformIO's installed tools and handles building, flashing and
USB configuration without a sequence of manual commands.

1. Enter Wi-Fi and connection settings with menu **1**.
2. Connect the camera's USB programmer base directly to the computer and choose **2**.
3. Connect the SmartDB main board through J4 USB-C and choose **3**.
4. Set protection limits using **4** when the installation settings are ready.

J6 USB-A is camera power only. It cannot program the camera. The camera sends images
over Wi-Fi; the MLX90640 thermal module connects to the S3 over I²C.

## Build targets

| Target | Hardware | Purpose |
|---|---|---|
| `smartdb_s3` | ESP32-S3-WROOM-1-N16R8 | Sensing, protection, fusion and telemetry |
| `esp32cam` | Separate AI Thinker ESP32-CAM | Fresh JPEG capture over Wi-Fi |
| `smartdb_s3_demo` | Same S3 board | Optional synthetic fusion demonstration; relay disabled |

Each target produces one application image assembled from its source files. Flash the
matching target onto each board. The shared project uses ESP-IDF, not Arduino `setup()`
and `loop()` entry points. Menu **7** builds or updates the normal S3/camera target; the
optional demo is available through PlatformIO's project tasks.

## Configuration and recovery

Wi-Fi, tokens, camera address and telemetry settings persist in the boards' NVS storage.
Menu **1** edits the local profile; **2** and **3** apply it to the corresponding board and
restart it. Later changes need no firmware rebuild. Protection settings are versioned and
persisted separately; updating them opens the relay and still requires physical re-arm.

Close other serial monitors before setup. If a port is absent, check the USB data cable
and programmer connection. If access is denied, check the operating system's serial-device
permissions. If the board does not answer, release BOOT/IO0 and tap RESET; older firmware
needs the setup-enabled update once. USB provisioning remains available without Wi-Fi.

See the [firmware guide](../../../../esp_idf/smartdb_fusion/README.md) for the complete
menu, storage behavior, manual build commands, calibration and troubleshooting. The
[older ESP-IDF workflow notes](../esp_idf/workflow.md) are background reference, not the
SmartDB v2 setup procedure.
