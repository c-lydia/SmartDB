#include "cloud_control.h"
#include "system_control.h"
#include "nvs.h"
#include <math.h>
#include <stdatomic.h>
#include <string.h>

typedef struct {
    uint64_t id;
    uint32_t interval;
    int32_t result;
} record_t;

static record_t applied = {.interval = 5};
static nvs_handle_t storage;
static bool available;
static atomic_uint interval_seconds = 5;

esp_err_t cloud_control_init(void) {
    esp_err_t e = nvs_open("cloud_control", NVS_READWRITE, &storage);

    if (e != ESP_OK) {
        return e;
    }

    record_t record = {0};
    size_t size = sizeof(record);
    e = nvs_get_blob(storage, "last", &record, &size);

    if (e == ESP_OK && size == sizeof(record) && record.interval >= 5 && record.interval <= 60) {
        applied = record;
    } else if (e != ESP_ERR_NVS_NOT_FOUND) {
        nvs_close(storage);
        return ESP_FAIL;
    }

    atomic_store(&interval_seconds, applied.interval);
    available = true;
    return ESP_OK;
}

unsigned cloud_control_interval(void) {
    return atomic_load(&interval_seconds);
}

static bool seconds(const cJSON *v, unsigned *out) {
    double n = cJSON_GetNumberValue(v);

    if (!cJSON_IsNumber(v) || !isfinite(n) || n < 5 || n > 60 || floor(n) != n) {
        return false;
    }

    *out = (unsigned)n;
    return true;
}

esp_err_t cloud_control_apply(const cJSON *command, uint64_t *id, bool *request_status) {
    *id = 0;
    *request_status = false;
    double number = cJSON_GetNumberValue(cJSON_GetObjectItemCaseSensitive(command, "command_id"));
    const char *name = cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(command, "command"));

    if (!cJSON_IsObject(command) || !name || !isfinite(number) || number < 1 ||
        number > 9007199254740991.0 || floor(number) != number) {
        return ESP_ERR_INVALID_ARG;
    }

    *id = (uint64_t)number;

    if (!available) {
        return ESP_ERR_INVALID_STATE;
    }

    if (*id == applied.id) {
        return (esp_err_t)applied.result;
    }

    if (*id < applied.id) {
        return ESP_ERR_INVALID_STATE;
    }

    unsigned interval = applied.interval;
    esp_err_t e = ESP_ERR_INVALID_ARG;
    const cJSON *value = cJSON_GetObjectItemCaseSensitive(command, "value");

    if (!strcmp(name, "OPEN_RELAY")) {
        system_request_open();
        e = ESP_OK;
    } else if (!strcmp(name, "REQUEST_STATUS")) {
        *request_status = true;
        e = ESP_OK;
    } else if (!strcmp(name, "SET_INTERVAL")) {
        if (seconds(value, &interval)) {
            e = ESP_OK;
        }
    } else if (
        !strcmp(name, "APPLY_CONFIG") && cJSON_IsObject(value) && cJSON_GetArraySize(value) == 3
    ) {
        const cJSON *current = cJSON_GetObjectItemCaseSensitive(value, "max_current");
        const cJSON *temperature = cJSON_GetObjectItemCaseSensitive(value, "max_temperature");

        if (cJSON_IsNumber(current) && cJSON_IsNumber(temperature) &&
            seconds(cJSON_GetObjectItemCaseSensitive(value, "sampling_rate"), &interval)) {
            cJSON *config = system_config_json();
            double version =
                cJSON_GetNumberValue(cJSON_GetObjectItemCaseSensitive(config, "version"));

            if (config && isfinite(version) && version < UINT32_MAX) {
                cJSON_ReplaceItemInObjectCaseSensitive(
                    config, "version", cJSON_CreateNumber(version + 1)
                );
                cJSON_ReplaceItemInObjectCaseSensitive(
                    config, "current_limit_a", cJSON_CreateNumber(current->valuedouble)
                );
                cJSON_ReplaceItemInObjectCaseSensitive(
                    config, "temperature_limit_c", cJSON_CreateNumber(temperature->valuedouble)
                );
                /* Preserve local scale and commissioned state. The shared validator opens the relay. */
                e = system_config_apply(config);
            }

            cJSON_Delete(config);
        }
    }

    record_t next = {.id = *id, .interval = e == ESP_OK ? interval : applied.interval, .result = e};
    esp_err_t saved = nvs_set_blob(storage, "last", &next, sizeof(next));

    if (saved == ESP_OK) {
        saved = nvs_commit(storage);
    }

    if (saved != ESP_OK) {
        system_request_open();
        return saved;
    }

    applied = next;
    atomic_store(&interval_seconds, applied.interval);
    return e;
}
