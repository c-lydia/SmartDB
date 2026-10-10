#pragma once
#include "esp_err.h"
#include "esp_http_server.h"
#include "fusion_core.h"
#include "cJSON.h"
esp_err_t system_start(void);
bool system_thermal_snapshot(fc_thermal_t *out);
void system_add_status(cJSON *root);
esp_err_t system_config_get(httpd_req_t *req);
esp_err_t system_config_set(httpd_req_t *req);
esp_err_t system_open(httpd_req_t *req);
cJSON *system_config_json(void);
esp_err_t system_config_apply(const cJSON *json);
void system_request_open(void);
