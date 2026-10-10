#pragma once
#include "fusion_core.h"
#include "esp_err.h"
esp_err_t thermal_init(void);
esp_err_t thermal_capture(fc_thermal_t *out);
