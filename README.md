
# SmartDB

SmartDB is a household electrical fault detection and protection system spanning ESP32
firmware, KiCad hardware, a device-ingestion gateway, API examples, and engineering
reference material.

## Project links

| Project | Hosted website | GitHub | Role |
|---|---|---|---|
| SmartDB | [Documentation](https://smartdb-docs.vercel.app) | [c-lydia/SmartDB](https://github.com/c-lydia/SmartDB) | Hardware, firmware, backend/API and engineering documentation |
| SmartDB documentation | [Current architecture](https://smartdb-docs.vercel.app/system/architecture.html) · [PCB downloads](https://smartdb-docs.vercel.app/hardware/index.html#files-and-previews) · [API/team handoff](https://smartdb-docs.vercel.app/system/index.html) | [Documentation sources](https://github.com/c-lydia/SmartDB/tree/main/docs) | Public documentation site |
| ByteLab | [ByteLab Web](https://bytelab-web.vercel.app) | [c-lydia/ByteLab](https://github.com/c-lydia/ByteLab) | Related firmware development workspace; desktop and browser editions |
| SmartDB user dashboard | Not published yet | Repository not available yet | Owned by the frontend team; links will be added when available |

ByteLab is a development companion, not SmartDB's user dashboard. The optional local
SmartDB developer console is for API testing and is not publicly deployed.

## Repository map

| Path | Contents |
|---|---|
| [`backend/`](backend/) | Python CoAP/CBOR ingestion gateway and tests |
| [`cloud/`](cloud/README.md) | Implemented Firebase HTTP API, emulator launcher and frontend integration guide |
| [`dashboard/`](dashboard/README.md) | Optional developer console; user dashboard belongs to the frontend team |
| [`esp_idf/smartdb_fusion/`](esp_idf/smartdb_fusion/README.md) | PlatformIO ESP-IDF v2 system firmware and separate ESP32-CAM firmware; build/flash guide |
| [`smart_db/`](smart_db/smart_db.kicad_pro) | Earlier KiCad design and historical manufacturing outputs |
| [`smart_db_v2/`](smart_db_v2/README.md) | Selected hardware revision; review findings and ESP32-S3 module decision |
| [`postman/`](postman/documents/README.md) | User-facing HTTP API requests, OpenAPI contract, and collection guide |
| [`docs/`](docs/) | System architecture and engineering references |

## Run the backend locally

Run `sh system.sh` from this folder (Node.js 22 LTS and Java 21+ required). It starts
Firebase emulators and the optional developer console, prints a local administrator login,
and preserves local data on clean shutdown. The API is at `http://127.0.0.1:5000/api/v1`.
See the [team API handoff](cloud/README.md) for integration, Postman, device provisioning,
configuration commands and deployment. The frontend team owns the user dashboard.

## Set up the two boards

The [web documentation source](docs/index.md) includes the setup guide, hardware notes,
API guide and architecture. Rebuild it with `./docs/build.sh` and open
`docs/_build/html/index.html`; see [website maintenance](docs/README.md).

Open `esp_idf/smartdb_fusion` as the VS Code project folder, then choose
**Terminal → Run Task → SmartDB: Setup**. Alternatively, launch the menu from that folder:

```sh
./setup.sh
```

Choose **1** to enter Wi-Fi settings, **2** to set up the ESP32-CAM, then **3** to set up
the SmartDB main board. The menu selects ports, offers the initial firmware flash, saves
settings and checks Wi-Fi. Use **4** for protection limits. Later connection changes are
saved over USB without rebuilding. The camera and main board each need their own firmware;
PlatformIO combines their source files automatically.

Connect each board directly to the computer for setup. The main board's J6 camera socket
supplies power only and cannot program the camera. See the [firmware guide](esp_idf/smartdb_fusion/README.md)
for connections, configuration, recovery and calibration. The [full architecture](docs/architecture_full_v1.1.md)
separates implemented bench behavior from production requirements; the [backend guide](backend/README.md)
covers the separate CoAP ingestion gateway.

## Current hardware

SmartDB v2 is being corrected for an ESP32-S3-WROOM-1-N16R8 module supplied and assembled
by JLCPCB. The existing ESP32-WROOM-32 development board is separate test hardware, not
the selected PCB module. The module replacement is applied in the KiCad
schematic and PCB, with corrected reset/boot wiring and an updated [pin map](smart_db_v2/pinmap.csv).
The current revision targets a **low-voltage bench load**, with corrected 5 V logic power,
USB, CT input and a separate normally-open relay contact connector. The permanent
[v2 project](smart_db_v2/smart_db/smart_db.kicad_pro) now contains the 95 × 78 mm
compact redesign with an AP63203 buck supply, four copper layers, and the SmartDB
logo and connector labels. All PCB connections are routed, with wider signal and power
traces and continuous inner ground planes. ERC, DRC, connectivity and schematic parity
checks report zero issues. See the [v2 review](smart_db_v2/README.md) for current validation results,
previews and the archived previous board. It is not a mains protection board.

## Project maturity

The v2 bench firmware now covers SCT-013 **isolated low-voltage AC** monitoring, MLX90640
thermal sensing, local relay protection with physical re-arm, persistent configuration/events,
registered RGB–thermal fusion and optional HTTPS diagnostic telemetry using the Postman
contract. Build `smartdb_s3` for the main board and `esp32cam` for the separate camera.
See the [firmware guide](esp_idf/smartdb_fusion/README.md) for configuration, flashing,
calibration and implementation limits. Source/build verification is complete; physical bench
validation remains pending. The PCB logic supply is DC; the CT measurement is AC-only.

This is an engineering-stage repository, not a production-certified safety device. The
backend's secure transport integration and several firmware/hardware validation activities
remain explicit pre-production work. Do not use it as the sole protective mechanism for a
live electrical installation.

## Related projects

- [ByteLab](https://github.com/c-lydia/ByteLab) — firmware development workspace; [hosted browser edition](https://bytelab-web.vercel.app) and [SmartDB integration guide](https://smartdb-docs.vercel.app/related/bytelab.html).
