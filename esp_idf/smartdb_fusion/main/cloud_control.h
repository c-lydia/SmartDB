#pragma once
#include "cJSON.h"
#include "esp_err.h"
#include <stdint.h>
#include <stdbool.h>
esp_err_t cloud_control_init(void);
unsigned cloud_control_interval(void);
/* Idempotent, ordered device commands. There is intentionally no arm operation. */
esp_err_t cloud_control_apply(const cJSON *command, uint64_t *id, bool *request_status);
