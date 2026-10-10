#pragma once
#include "esp_err.h"
#include "cJSON.h"
typedef struct {
    char wifi_ssid[33], wifi_password[64], api_token[97];
    char camera_url[192], camera_id[64], installation_id[64];
    char telemetry_url[256], telemetry_token[701];
} device_settings_t;
/* Immutable active settings for this boot. Saved changes take effect after restart. */
esp_err_t device_settings_init(void);
const device_settings_t *device_settings(void);
cJSON *device_settings_public(void);
esp_err_t device_settings_save(const cJSON *json);
