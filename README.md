
# SmartDB

SmartDB is a household electrical fault detection and protection system spanning ESP32
firmware, KiCad hardware, a device-ingestion gateway, API examples, and engineering
reference material.

## Repository map

| Path | Contents |
|---|---|
| [`backend/`](backend/) | Python CoAP/CBOR ingestion gateway and tests |
| [`esp_idf/`](esp_idf/) | ESP-IDF/PlatformIO firmware experiments and ESP32-CAM project |
| [`smart_db/`](smart_db/) | Primary KiCad design and manufacturing outputs |
| [`smart_db_v2/`](smart_db_v2/) | Version 2 KiCad design |
| [`postman/`](postman/) | User-facing HTTP API requests, OpenAPI contract, and [collection guide](postman/documentation/README.md) |
| [`docs/`](docs/) | System architecture and engineering references |

Start with the [full architecture](docs/architecture_full_v1.1.md) for system requirements
and the [backend guide](backend/README.md) to run the currently implemented gateway.

## Project maturity

This is an engineering-stage repository, not a production-certified safety device. The
backend's secure transport integration and several firmware/hardware validation activities
remain explicit pre-production work. Do not use it as the sole protective mechanism for a
live electrical installation.

## Related projects

- [ByteLab](https://github.com/c-lydia/ByteLab) — companion Flutter app for device control/monitoring
