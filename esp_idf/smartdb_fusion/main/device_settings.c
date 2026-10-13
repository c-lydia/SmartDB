#include "device_settings.h"
#include "project_config.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "esp_log.h"
#include <string.h>
#include <stddef.h>
#include <stdio.h>
static device_settings_t active;

typedef struct {
    const char *name;
    size_t offset, size;
    bool secret;
} field_t;

#define FIELD(name, secret) {#name, offsetof(device_settings_t, name), sizeof(active.name), secret}
static const field_t fields[] = {
    FIELD(wifi_ssid, false),
    FIELD(wifi_password, true),
    FIELD(api_token, true),
    FIELD(camera_url, false),
    FIELD(camera_id, false),
    FIELD(installation_id, false),
    FIELD(telemetry_url, false),
    FIELD(telemetry_token, true)
};

static bool printable(const char *s) {
    for (; *s; s++) {
        if ((unsigned char)*s < 32 || (unsigned char)*s == 127) {
            return false;
        }
    }

    return true;
}

static bool token(const char *s, size_t min, size_t max) {
    size_t n = strlen(s);

    if (n < min || n > max) {
        return false;
    }

    for (; *s; s++) {
        if ((unsigned char)*s < 33 || (unsigned char)*s > 126) {
            return false;
        }
    }

    return true;
}

static bool url(const char *s, const char *scheme) {
    size_t n = strlen(scheme);

    if (strncmp(s, scheme, n)) {
        return false;
    }

    const char *host = s + n, *end = strchr(host, '/');

    if (!*host || host == end || *host == '?' || *host == '#') {
        return false;
    }

    for (; *s; s++) {
        if ((unsigned char)*s <= 32 || (unsigned char)*s > 126 || *s == '@' || *s == '#') {
            return false;
        }
    }

    return true;
}

static bool valid(const device_settings_t *s) {
    for (unsigned i = 0; i < sizeof(fields) / sizeof(fields[0]); i++) {
        const char *v = (const char *)s + fields[i].offset;

        if (!memchr(v, 0, fields[i].size) || !printable(v)) {
            return false;
        }
    }

    return s->wifi_ssid[0] && strlen(s->wifi_password) >= 8 && token(s->api_token, 24, 96) &&
        url(s->camera_url, "http://") && s->camera_id[0] && s->installation_id[0] &&
        (!s->telemetry_url[0] ||
            (url(s->telemetry_url, "https://") && token(s->telemetry_token, 1, 700)));
}

esp_err_t device_settings_init(void) {
    esp_err_t e = nvs_flash_init();

    if (e != ESP_OK) {
        return e;
    }

    active = (device_settings_t){
        .wifi_ssid = SMARTDB_WIFI_SSID,
        .wifi_password = SMARTDB_WIFI_PASSWORD,
        .api_token = SMARTDB_API_TOKEN,
        .camera_url = SMARTDB_CAMERA_URL,
        .camera_id = SMARTDB_CAMERA_ID,
        .installation_id = SMARTDB_INSTALLATION_ID,
        .telemetry_url = SMARTDB_TELEMETRY_URL,
        .telemetry_token = SMARTDB_TELEMETRY_TOKEN
    };
    nvs_handle_t h;
    e = nvs_open("connection", NVS_READWRITE, &h);

    if (e != ESP_OK) {
        return e;
    }

    device_settings_t saved;
    size_t size = sizeof(saved);
    e = nvs_get_blob(h, "settings_v1", &saved, &size);
    nvs_close(h);

    if (e == ESP_OK && size == sizeof(saved) && valid(&saved)) {
        active = saved;
    } else if (e != ESP_ERR_NVS_NOT_FOUND) {
        /* Keep USB recovery available instead of boot-looping on a damaged record. */
        active.wifi_ssid[0] = 0;
        active.api_token[0] = 0;
        ESP_LOGE("settings", "Saved connection settings unreadable; reconfigure through USB setup");
    }

    return ESP_OK;
}

const device_settings_t *device_settings(void) {
    return &active;
}

cJSON *device_settings_public(void) {
    cJSON *j = cJSON_CreateObject();

    if (!j) {
        return NULL;
    }

    for (unsigned i = 0; i < sizeof(fields) / sizeof(fields[0]); i++) {
        const field_t *f = &fields[i];
        const char *v = (const char *)&active + f->offset;

        if (f->secret) {
            char key[64];
            snprintf(key, sizeof(key), "%s_set", f->name);
            cJSON_AddBoolToObject(j, key, v[0] != 0);
        } else {
            cJSON_AddStringToObject(j, f->name, v);
        }
    }

    return j;
}

esp_err_t device_settings_save(const cJSON *json) {
    /* Complete replacement avoids ambiguous retained secrets and partially applied updates. */
    if (!cJSON_IsObject(json) || cJSON_GetArraySize(json) != 8) {
        return ESP_ERR_INVALID_ARG;
    }

    device_settings_t next = {0};

    for (unsigned i = 0; i < sizeof(fields) / sizeof(fields[0]); i++) {
        const field_t *f = &fields[i];
        const cJSON *v = cJSON_GetObjectItemCaseSensitive(json, f->name);

        if (!cJSON_IsString(v) || strlen(v->valuestring) >= f->size) {
            return ESP_ERR_INVALID_ARG;
        }

        memcpy((char *)&next + f->offset, v->valuestring, strlen(v->valuestring) + 1);
    }

    if (!valid(&next)) {
        return ESP_ERR_INVALID_ARG;
    }

    nvs_handle_t h;
    esp_err_t e = nvs_open("connection", NVS_READWRITE, &h);

    if (e != ESP_OK) {
        return e;
    }

    e = nvs_set_blob(h, "settings_v1", &next, sizeof(next));

    if (e == ESP_OK) {
        e = nvs_commit(h);
    }

    nvs_close(h);
    memset(&next, 0, sizeof(next));
    return e;
}
