
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
| [`esp_idf/`](esp_idf/) | ESP-IDF/PlatformIO firmware experiments and ESP32-CAM project |
| [`smart_db/`](smart_db/) | Primary KiCad design and manufacturing outputs |
| [`smart_db_v2/`](smart_db_v2/) | Version 2 KiCad design |
| [`postman/`](postman/) | User-facing HTTP API requests, OpenAPI contract, and [collection guide](postman/documents/README.md) |
| [`docs/`](docs/) | System architecture and engineering references |

Start with the [full architecture](docs/architecture_full_v1.1.md) for system requirements
and the [backend guide](backend/README.md) to run the currently implemented gateway.

## Project maturity

This is an engineering-stage repository, not a production-certified safety device. The
backend's secure transport integration and several firmware/hardware validation activities
remain explicit pre-production work. Do not use it as the sole protective mechanism for a
live electrical installation.

## Related projects

- [ByteLab](https://github.com/c-lydia/ByteLab) — firmware development workspace; [hosted browser edition](https://bytelab-web.vercel.app) and [SmartDB integration guide](https://smartdb-docs.vercel.app/related/bytelab.html).
