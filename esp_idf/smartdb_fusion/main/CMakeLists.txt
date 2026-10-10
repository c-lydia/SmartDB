if(IDF_TARGET STREQUAL "esp32s3")
    idf_component_register(SRCS "app_s3.c" "network.c" "thermal_sensor.c" "sensor_bus.c" "system_control.c" "telemetry.c" "cloud_control.c" "device_settings.c" "serial_setup.c"
        INCLUDE_DIRS "." "../config"
        REQUIRES fusion_core mlx90640 esp_jpeg esp_http_client esp_http_server
                 esp_wifi esp_event esp_netif nvs_flash esp_timer esp_driver_gpio esp_driver_i2c esp_driver_uart cjson mbedtls)
else()
    idf_component_register(SRCS "app_camera.c" "network.c" "device_settings.c" "serial_setup.c"
        INCLUDE_DIRS "." "../config"
        REQUIRES esp32-camera esp_http_server esp_wifi esp_event esp_netif
                 nvs_flash esp_timer esp_driver_uart cjson)
endif()
