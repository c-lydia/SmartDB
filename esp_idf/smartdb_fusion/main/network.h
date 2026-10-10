#pragma once
#include "esp_http_server.h"
#include "esp_err.h"
#include <stdint.h>
uint32_t network_ipv4(void);
esp_err_t network_start(void);
bool request_authorized(httpd_req_t *req);
httpd_handle_t web_server_start(void);
