#pragma once
#include "driver/i2c_master.h"
esp_err_t sensor_bus_init(void);
esp_err_t sensor_bus_device(uint8_t address,i2c_master_dev_handle_t *out);
