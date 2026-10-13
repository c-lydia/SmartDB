#include "cloud_control.h"
#include "system_control.h"
#include "nvs.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static unsigned char saved[64], pending[64];
static size_t saved_size;
static bool exists, fail_commit;
static unsigned opens, updates;

esp_err_t nvs_open(const char *name, int mode, nvs_handle_t *h) {
    (void)mode;
    assert(!strcmp(name, "cloud_control"));
    *h = 1;
    return ESP_OK;
}

void nvs_close(nvs_handle_t h) {
    (void)h;
}

esp_err_t nvs_get_blob(nvs_handle_t h, const char *key, void *data, size_t *size) {
    (void)h;
    assert(!strcmp(key, "last"));

    if (!exists) {
        return ESP_ERR_NVS_NOT_FOUND;
    }

    assert(*size >= saved_size);
    memcpy(data, saved, saved_size);
    *size = saved_size;
    return ESP_OK;
}

esp_err_t nvs_set_blob(nvs_handle_t h, const char *key, const void *data, size_t size) {
    (void)h;
    assert(!strcmp(key, "last"));
    assert(size <= sizeof(saved));
    memcpy(pending, data, size);
    saved_size = size;
    return ESP_OK;
}

esp_err_t nvs_commit(nvs_handle_t h) {
    (void)h;

    if (fail_commit) {
        return ESP_FAIL;
    }

    memcpy(saved, pending, saved_size);
    exists = true;
    return ESP_OK;
}

void system_request_open(void) {
    opens++;
}

cJSON *system_config_json(void) {
    return cJSON_Parse(
        "{\"version\":4,\"commissioned\":false,\"current_limit_a\":0.8,"
        "\"temperature_limit_c\":60,\"current_scale_a_per_v\":111}"
    );
}

esp_err_t system_config_apply(const cJSON *j) {
    assert(cJSON_GetNumberValue(cJSON_GetObjectItem(j, "version")) == 5);
    assert(cJSON_IsFalse(cJSON_GetObjectItem(j, "commissioned")));
    assert(cJSON_GetNumberValue(cJSON_GetObjectItem(j, "current_scale_a_per_v")) == 111);
    assert(cJSON_GetNumberValue(cJSON_GetObjectItem(j, "current_limit_a")) == .7);
    assert(cJSON_GetNumberValue(cJSON_GetObjectItem(j, "temperature_limit_c")) == 55);
    updates++;
    system_request_open();
    return ESP_OK;
}

static esp_err_t apply(const char *json, uint64_t expected, bool requested) {
    cJSON *j = cJSON_Parse(json);
    uint64_t id = 0;
    bool fresh = false;
    esp_err_t e = cloud_control_apply(j, &id, &fresh);
    cJSON_Delete(j);
    assert(id == expected);
    assert(fresh == requested);
    return e;
}

int main(void) {
    assert(cloud_control_init() == ESP_OK);
    assert(cloud_control_interval() == 5);
    assert(apply("{\"command_id\":1,\"command\":\"OPEN_RELAY\"}", 1, false) == ESP_OK);
    assert(opens == 1);
    assert(apply("{\"command_id\":1,\"command\":\"OPEN_RELAY\"}", 1, false) == ESP_OK);
    assert(opens == 1);
    assert(cloud_control_init() == ESP_OK);
    assert(apply("{\"command_id\":1,\"command\":\"OPEN_RELAY\"}", 1, false) == ESP_OK);
    assert(opens == 1);
    assert(
        apply("{\"command_id\":2,\"command\":\"CLOSE_RELAY\"}", 2, false) == ESP_ERR_INVALID_ARG
    );
    assert(
        apply("{\"command_id\":3,\"command\":\"SET_INTERVAL\",\"value\":1}", 3, false) ==
        ESP_ERR_INVALID_ARG
    );
    assert(cloud_control_interval() == 5);
    assert(
        apply("{\"command_id\":4,\"command\":\"SET_INTERVAL\",\"value\":10}", 4, false) == ESP_OK
    );
    assert(cloud_control_interval() == 10);
    assert(
        apply(
            "{\"command_id\":5,\"command\":\"APPLY_CONFIG\",\"value\":{\"max_current\":0.7,"
            "\"max_temperature\":55,\"sampling_rate\":15}}",
            5,
            false
        ) == ESP_OK
    );
    assert(updates == 1);
    assert(opens == 2);
    assert(cloud_control_interval() == 15);
    assert(apply("{\"command_id\":6,\"command\":\"REQUEST_STATUS\"}", 6, true) == ESP_OK);
    assert(
        apply("{\"command_id\":5,\"command\":\"OPEN_RELAY\"}", 5, false) == ESP_ERR_INVALID_STATE
    );
    assert(
        apply("{\"command_id\":1.5,\"command\":\"OPEN_RELAY\"}", 0, false) == ESP_ERR_INVALID_ARG
    );
    fail_commit = true;
    assert(
        apply("{\"command_id\":7,\"command\":\"SET_INTERVAL\",\"value\":30}", 7, false) == ESP_FAIL
    );
    assert(opens == 3);
    assert(cloud_control_interval() == 15);
    puts(
        "Cloud command tests passed: no arm, ordered retry/reboot handling, bounds, calibration "
        "preservation and storage failure."
    );
}
