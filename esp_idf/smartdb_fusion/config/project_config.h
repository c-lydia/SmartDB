#pragma once
/* Optional build defaults. USB setup/NVS overrides connection settings at runtime. */
#if __has_include("local_config.h")
#include "local_config.h"
#endif
#ifndef SMARTDB_WIFI_SSID
#define SMARTDB_WIFI_SSID ""
#endif
#ifndef SMARTDB_WIFI_PASSWORD
#define SMARTDB_WIFI_PASSWORD ""
#endif
#ifndef SMARTDB_API_TOKEN
#define SMARTDB_API_TOKEN ""
#endif
#ifndef SMARTDB_CAMERA_URL
#define SMARTDB_CAMERA_URL "http://192.168.1.50/capture"
#endif
#ifndef SMARTDB_CAMERA_ID
#define SMARTDB_CAMERA_ID "smartdb-camera-1"
#endif
#ifndef SMARTDB_INSTALLATION_ID
#define SMARTDB_INSTALLATION_ID "panel-1"
#endif
#ifndef SMARTDB_EMISSIVITY
#define SMARTDB_EMISSIVITY 0.95f
#endif
#ifndef SMARTDB_REFLECTED_OFFSET_C
#define SMARTDB_REFLECTED_OFFSET_C 8.0f
#endif
#define SMARTDB_MAX_JPEG (128 * 1024)
#define SMARTDB_FRAME_WIDTH 320
#define SMARTDB_FRAME_HEIGHT 240
#define SMARTDB_PAIR_WINDOW_US 500000
#define SMARTDB_MAX_AGE_US 2000000
#ifndef SMARTDB_DEMO
#define SMARTDB_DEMO 0
#endif
#ifndef SMARTDB_ACTIVE_BUZZER
#define SMARTDB_ACTIVE_BUZZER 0
#endif
#ifndef SMARTDB_TELEMETRY_URL
#define SMARTDB_TELEMETRY_URL ""
#endif
#ifndef SMARTDB_TELEMETRY_TOKEN
#define SMARTDB_TELEMETRY_TOKEN ""
#endif
#ifndef SMARTDB_SNTP_SERVER
#define SMARTDB_SNTP_SERVER "pool.ntp.org"
#endif
