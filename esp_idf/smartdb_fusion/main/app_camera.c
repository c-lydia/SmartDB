#include "device_settings.h"
#include "serial_setup.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "project_config.h"
#include "network.h"
#include "esp_camera.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "esp_log.h"
#include <inttypes.h>
#include <stdio.h>
static uint32_t sequence, boot;
static bool camera_ready;

static esp_err_t capture(httpd_req_t *req) {
    if (!request_authorized(req)) {
        return ESP_OK;
    }

    if (!camera_ready) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "Camera initialization failed; check camera connection");
    }

    int64_t requested = esp_timer_get_time();
    camera_fb_t *fb = NULL;
    /* A queued buffer may predate the request. Discard it, retaining a bounded attempt count. */
    for (int i = 0; i < 4; i++) {
        fb = esp_camera_fb_get();

        if (!fb) {
            break;
        }

        int64_t captured = (int64_t)fb->timestamp.tv_sec * 1000000 + fb->timestamp.tv_usec;

        if (captured >= requested && fb->format == PIXFORMAT_JPEG && fb->width == 320 &&
            fb->height == 240 && fb->len <= SMARTDB_MAX_JPEG) {
            break;
        }

        esp_camera_fb_return(fb);
        fb = NULL;
    }

    if (!fb) {
        httpd_resp_set_status(req, "503 Service Unavailable");
        return httpd_resp_sendstr(req, "Fresh camera frame unavailable");
    }

    char boot_text[16], seq_text[16];
    snprintf(boot_text, sizeof(boot_text), "%08" PRIx32, boot);
    snprintf(seq_text, sizeof(seq_text), "%" PRIu32, ++sequence);
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "X-Camera-ID", device_settings()->camera_id);
    httpd_resp_set_hdr(req, "X-Camera-Boot", boot_text);
    httpd_resp_set_hdr(req, "X-Camera-Sequence", seq_text);
    httpd_resp_set_hdr(req, "X-Capture-Policy", "fresh-after-request");
    esp_err_t err = httpd_resp_send(req, (const char *)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    return err;
}

void app_main(void) {
    ESP_ERROR_CHECK(device_settings_init());
    ESP_ERROR_CHECK(serial_setup_start());
    /* AI Thinker ESP32-CAM: PWDN GPIO32, unlike the older diagnostic configuration. */
    camera_config_t cfg = {
        .pin_pwdn = 32,
        .pin_reset = -1,
        .pin_xclk = 0,
        .pin_sccb_sda = 26,
        .pin_sccb_scl = 27,
        .pin_d7 = 35,
        .pin_d6 = 34,
        .pin_d5 = 39,
        .pin_d4 = 36,
        .pin_d3 = 21,
        .pin_d2 = 19,
        .pin_d1 = 18,
        .pin_d0 = 5,
        .pin_vsync = 25,
        .pin_href = 23,
        .pin_pclk = 22,
        .xclk_freq_hz = 20000000,
        .ledc_timer = LEDC_TIMER_0,
        .ledc_channel = LEDC_CHANNEL_0,
        .pixel_format = PIXFORMAT_JPEG,
        .frame_size = FRAMESIZE_QVGA,
        .jpeg_quality = 12,
        .fb_count = 1,
        .fb_location = CAMERA_FB_IN_PSRAM,
        .grab_mode = CAMERA_GRAB_WHEN_EMPTY
    };
    camera_ready = esp_camera_init(&cfg) == ESP_OK;

    if (!camera_ready) {
        ESP_LOGE("camera", "Camera unavailable; USB and Wi-Fi setup remain available");
    }

    boot = esp_random();

    if (network_start() != ESP_OK) {
        ESP_LOGW("camera", "Use USB setup to configure Wi-Fi");
        return;
    }

    httpd_handle_t h = web_server_start();
    httpd_uri_t uri = {.uri = "/capture", .method = HTTP_GET, .handler = capture};
    ESP_ERROR_CHECK(httpd_register_uri_handler(h, &uri));
    ESP_LOGI("camera", "Fresh QVGA JPEG endpoint ready; SD and flash LED unused");
}
