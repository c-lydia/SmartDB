#pragma once
/* Optional build-time fallback. Prefer ./setup.sh; saved NVS connection settings take precedence. */
#define SMARTDB_WIFI_SSID "your-isolated-network"
#define SMARTDB_WIFI_PASSWORD "your-wifi-password"
/* Same random token (at least 24 characters) in both builds. Never commit it. */
#define SMARTDB_API_TOKEN ""
#define SMARTDB_CAMERA_URL "http://192.168.1.50/capture"
#define SMARTDB_CAMERA_ID "smartdb-camera-1"
#define SMARTDB_INSTALLATION_ID "panel-1"
/* Surface assumptions, not universal temperature calibration. */
#define SMARTDB_EMISSIVITY 0.95f
#define SMARTDB_REFLECTED_OFFSET_C 8.0f
/* Existing Postman diagnostic telemetry route. Empty disables uploads. */
#define SMARTDB_TELEMETRY_URL ""
#define SMARTDB_TELEMETRY_TOKEN ""
/* Set to 1 only after selecting an active buzzer for BZ1. */
#define SMARTDB_ACTIVE_BUZZER 0
