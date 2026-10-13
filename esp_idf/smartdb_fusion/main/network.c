#include "device_settings.h"
#include "network.h"
#include "project_config.h"
#include <string.h>
#include <stdio.h>
#include <stdatomic.h>
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/event_groups.h"
static EventGroupHandle_t events;
static atomic_uint_least32_t current_ip;

uint32_t network_ipv4(void) {
    return atomic_load(&current_ip);
}

static void changed(void *arg, esp_event_base_t base, int32_t id, void *data) {
    (void)arg;

    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    }

    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        atomic_store(&current_ip, 0);
        xEventGroupClearBits(events, 1);
        esp_wifi_connect();
    }

    if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *e = data;
        atomic_store(&current_ip, e->ip_info.ip.addr);
        ESP_LOGI("network", "IP: " IPSTR, IP2STR(&e->ip_info.ip));
        xEventGroupSetBits(events, 1);
    }
}

esp_err_t network_start(void) {
    size_t ssid = strlen(device_settings()->wifi_ssid),
           pw = strlen(device_settings()->wifi_password),
           token = strlen(device_settings()->api_token);

    if (!ssid || ssid > 32 || pw < 8 || pw > 63 || token < 24 || token > 96) {
        ESP_LOGE("network", "Wi-Fi not configured; use the SmartDB USB setup menu");
        return ESP_ERR_INVALID_ARG;
    }

    for (size_t i = 0; i < token; i++) {
        if (device_settings()->api_token[i] < 33 || device_settings()->api_token[i] > 126) {
            return ESP_ERR_INVALID_ARG;
        }
    }

    /* Preserve existing NVS on errors; do not silently erase provisioning data. */
    esp_err_t err = nvs_flash_init();

    if (err != ESP_OK) {
        return err;
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    events = xEventGroupCreate();

    if (!events) {
        return ESP_ERR_NO_MEM;
    }

    esp_netif_create_default_wifi_sta();
    wifi_init_config_t init = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&init));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, changed, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, changed, NULL));
    wifi_config_t cfg = {0};
    memcpy(cfg.sta.ssid, device_settings()->wifi_ssid, ssid);
    memcpy(cfg.sta.password, device_settings()->wifi_password, pw);
    cfg.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &cfg));
    ESP_ERROR_CHECK(esp_wifi_start());

    while (!(xEventGroupWaitBits(events, 1, pdFALSE, pdTRUE, pdMS_TO_TICKS(30000)) & 1)) {
        ESP_LOGW("network", "Waiting for Wi-Fi; local control stays active");
    }

    return ESP_OK;
}

bool request_authorized(httpd_req_t *req) {
    char actual[128] = {0}, expected[128];
    snprintf(expected, sizeof(expected), "Bearer %s", device_settings()->api_token);
    size_t len = httpd_req_get_hdr_value_len(req, "Authorization");
    bool ok = len == strlen(expected) && len < sizeof(actual) &&
        httpd_req_get_hdr_value_str(req, "Authorization", actual, sizeof(actual)) == ESP_OK;
    unsigned diff = 0;

    for (size_t i = 0; ok && i < len; i++) {
        diff |= (unsigned char)actual[i] ^ (unsigned char)expected[i];
    }

    if (!ok || diff) {
        httpd_resp_set_status(req, "401 Unauthorized");
        httpd_resp_sendstr(req, "Authentication required");
        return false;
    }

    httpd_resp_set_hdr(req, "Cache-Control", "no-store");
    return true;
}

httpd_handle_t web_server_start(void) {
    httpd_config_t c = HTTPD_DEFAULT_CONFIG();
    c.stack_size = 8192;
    c.max_uri_handlers = 8;
    c.recv_wait_timeout = 3;
    c.send_wait_timeout = 3;
    c.lru_purge_enable = true;
    httpd_handle_t h = NULL;
    ESP_ERROR_CHECK(httpd_start(&h, &c));
    return h;
}
