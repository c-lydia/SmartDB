#include "sensor_bus.h"
static i2c_master_bus_handle_t bus;

esp_err_t sensor_bus_init(void) {
    i2c_master_bus_config_t cfg = {
        .i2c_port = I2C_NUM_0,
        .sda_io_num = 10,
        .scl_io_num = 2,
        .clk_source = I2C_CLK_SRC_DEFAULT,
        .glitch_ignore_cnt = 7,
        .flags.enable_internal_pullup = true
    };
    return i2c_new_master_bus(&cfg, &bus);
}

esp_err_t sensor_bus_device(uint8_t address, i2c_master_dev_handle_t *out) {
    i2c_device_config_t cfg = {
        .dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = address, .scl_speed_hz = 400000
    };
    return i2c_master_bus_add_device(bus, &cfg, out);
}
