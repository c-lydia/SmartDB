/* Copied from src/main.c to place app source in ESP-IDF `main/` component */
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_camera.h"
#include "driver/gpio.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include <lwip/inet.h>

/* Minimal SCCB prototypes to avoid including private component headers */
extern int SCCB_Init(int pin_sda, int pin_scl);
extern int SCCB_Probe(uint8_t slv_addr);
extern int SCCB_Deinit(void);

#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "sdmmc_cmd.h"

#define TAG "esp32cam_test"

/* Configuration toggles - edit as needed */
#define ENABLE_AP 1           // 1: start WiFi SoftAP, 0: skip
#define AP_SSID "esp_not_esp-ing"
#define AP_PASS "SmartDBesp32cam"
#define AP_CHANNEL 1
#define AP_MAX_CONN 4

#define ENABLE_SD 1           // 1: attempt SDMMC mount, 0: skip SD init

#define CAM_PIN_PWDN    -1
#define CAM_PIN_RESET   -1   // not connected on AI Thinker
#define CAM_PIN_XCLK     0
#define CAM_PIN_SIOD    26   // SDA
#define CAM_PIN_SIOC    27   // SCL
#define CAM_PIN_D7      35
#define CAM_PIN_D6      34
#define CAM_PIN_D5      39
#define CAM_PIN_D4      36
#define CAM_PIN_D3      21
#define CAM_PIN_D2      19
#define CAM_PIN_D1      18
#define CAM_PIN_D0       5
#define CAM_PIN_VSYNC   25
#define CAM_PIN_HREF    23
#define CAM_PIN_PCLK    22

static camera_config_t camera_config = {
    .pin_pwdn     = CAM_PIN_PWDN,
    .pin_reset    = CAM_PIN_RESET,
    .pin_xclk     = CAM_PIN_XCLK,
    .pin_sccb_sda = CAM_PIN_SIOD,
    .pin_sccb_scl = CAM_PIN_SIOC,

    .sccb_i2c_port = 1,

    .pin_d7       = CAM_PIN_D7,
    .pin_d6       = CAM_PIN_D6,
    .pin_d5       = CAM_PIN_D5,
    .pin_d4       = CAM_PIN_D4,
    .pin_d3       = CAM_PIN_D3,
    .pin_d2       = CAM_PIN_D2,
    .pin_d1       = CAM_PIN_D1,
    .pin_d0       = CAM_PIN_D0,

    .pin_vsync    = CAM_PIN_VSYNC,
    .pin_href     = CAM_PIN_HREF,
    .pin_pclk     = CAM_PIN_PCLK,

    .xclk_freq_hz = 24000000,           // 24MHz XCLK (OV3660 prefers 24MHz)
    .ledc_timer   = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,

    .pixel_format = PIXFORMAT_JPEG,     // JPEG output
    .frame_size   = FRAMESIZE_QVGA,     // 320x240 — good starting point

    .jpeg_quality = 12,                 // 0-63, lower = higher quality
    .fb_count     = 1,                  // 1 frame buffer (use DRAM fallback)
    .fb_location  = CAMERA_FB_IN_DRAM,  // use internal RAM for frame buffer
    .grab_mode    = CAMERA_GRAB_WHEN_EMPTY,
};

static sdmmc_card_t *sd_card = NULL;
static bool sd_mounted = false;

static esp_err_t sd_init(void) {
    ESP_LOGI(TAG, "Initialising SD card...");

    sdmmc_host_t host = SDMMC_HOST_DEFAULT();

    sdmmc_slot_config_t slot_config = SDMMC_SLOT_CONFIG_DEFAULT();
    slot_config.width = 1;   // 1-bit mode (AI Thinker only has 1-bit SD)

    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,  // don't auto-format
        .max_files              = 5,
        .allocation_unit_size   = 16 * 1024,
    };

    esp_err_t ret = esp_vfs_fat_sdmmc_mount(
        "/sdcard", &host, &slot_config, &mount_config, &sd_card
    );

    if (ret != ESP_OK) {
        if (ret == ESP_FAIL) {
            ESP_LOGE(TAG, "SD mount failed — check format (must be FAT32)");
        } else {
            ESP_LOGE(TAG, "SD init failed: %s", esp_err_to_name(ret));
        }
        return ret;
    }

    sdmmc_card_print_info(stdout, sd_card);
    sd_mounted = true;
    ESP_LOGI(TAG, "SD card mounted at /sdcard");
    return ESP_OK;
}

static void wifi_init_softap(void) {
    ESP_LOGI(TAG, "Starting WiFi SoftAP '%s'...", AP_SSID);

    // Initialize TCP/IP and NVS if not already done by the app
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    if (ret != ESP_OK) {
        ESP_LOGW(TAG, "NVS init for WiFi failed: %s", esp_err_to_name(ret));
    }

    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_t *ap_netif = esp_netif_create_default_wifi_ap();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    wifi_config_t wifi_config = { 0 };
    strncpy((char *)wifi_config.ap.ssid, AP_SSID, sizeof(wifi_config.ap.ssid)-1);
    wifi_config.ap.ssid_len = strlen(AP_SSID);
    strncpy((char *)wifi_config.ap.password, AP_PASS, sizeof(wifi_config.ap.password)-1);
    wifi_config.ap.channel = AP_CHANNEL;
    wifi_config.ap.max_connection = AP_MAX_CONN;
    wifi_config.ap.authmode = (strlen(AP_PASS) == 0) ? WIFI_AUTH_OPEN : WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_AP));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_AP, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    ESP_LOGI(TAG, "WiFi SoftAP started. SSID:'%s' password:'%s'", AP_SSID, AP_PASS[0] ? AP_PASS : "(open)");

    if (ap_netif) {
        esp_netif_ip_info_t ip_info;
        if (esp_netif_get_ip_info(ap_netif, &ip_info) == ESP_OK) {
            uint32_t ip = ip_info.ip.addr;
            ESP_LOGI(TAG, "AP IP: %u.%u.%u.%u",
                     (unsigned)(ip & 0xFF),
                     (unsigned)((ip >> 8) & 0xFF),
                     (unsigned)((ip >> 16) & 0xFF),
                     (unsigned)((ip >> 24) & 0xFF));
        }
    }
}

static esp_err_t camera_init(void) {
    ESP_LOGI(TAG, "Initialising camera...");

    esp_err_t ret = esp_camera_init(&camera_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed: %s", esp_err_to_name(ret));
        return ret;
    }

    // get sensor handle to adjust settings
    sensor_t *s = esp_camera_sensor_get();
    if (s == NULL) {
        ESP_LOGE(TAG, "Could not get sensor handle");
        return ESP_FAIL;
    }

    // log sensor info
    ESP_LOGI(TAG, "Camera sensor PID: 0x%02X", s->id.PID);

    // optional sensor adjustments
    s->set_brightness(s, 0);    // -2 to 2
    s->set_contrast(s, 0);      // -2 to 2
    s->set_saturation(s, 0);    // -2 to 2
    s->set_whitebal(s, 1);      // auto white balance on
    s->set_exposure_ctrl(s, 1); // auto exposure on

    ESP_LOGI(TAG, "Camera initialised successfully");
    return ESP_OK;
}

static void sccb_debug_scan(void) {
    ESP_LOGI(TAG, "Starting SCCB debug scan (this may take a few seconds)...");
    int init_ret = SCCB_Init(CAM_PIN_SIOD, CAM_PIN_SIOC);
    if (init_ret != ESP_OK) {
        ESP_LOGE(TAG, "SCCB debug init failed: %s", esp_err_to_name(init_ret));
        return;
    }
    for (int addr = 0x03; addr <= 0x77; addr++) {
        esp_err_t probe = SCCB_Probe(addr);
        if (probe != ESP_OK) {
            ESP_LOGD(TAG, "No device at addr 0x%02x (%d)", addr, probe);
            continue;
        }
        ESP_LOGI(TAG, "Device responded at SCCB addr=0x%02x", addr);
    }
    ESP_LOGI(TAG, "SCCB debug scan complete");
    /* Deinitialise SCCB so camera_init can acquire the I2C bus itself */
    int deinit_ret = SCCB_Deinit();
    if (deinit_ret != ESP_OK) {
        ESP_LOGE(TAG, "SCCB debug deinit failed: %s", esp_err_to_name(deinit_ret));
    }
}

static void gpio_level_check(int sda_pin, int scl_pin) {
    ESP_LOGI(TAG, "GPIO-level check: SDA=%d SCL=%d", sda_pin, scl_pin);

    gpio_reset_pin(sda_pin);
    gpio_reset_pin(scl_pin);

    gpio_set_direction(sda_pin, GPIO_MODE_INPUT);
    gpio_set_direction(scl_pin, GPIO_MODE_INPUT);

    int sda_lv = gpio_get_level(sda_pin);
    int scl_lv = gpio_get_level(scl_pin);
    ESP_LOGI(TAG, "  initial: SDA=%d SCL=%d", sda_lv, scl_lv);

    gpio_set_pull_mode(sda_pin, GPIO_PULLUP_ONLY);
    gpio_set_pull_mode(scl_pin, GPIO_PULLUP_ONLY);
    vTaskDelay(pdMS_TO_TICKS(10));

    sda_lv = gpio_get_level(sda_pin);
    scl_lv = gpio_get_level(scl_pin);
    ESP_LOGI(TAG, "  with internal pull-ups: SDA=%d SCL=%d", sda_lv, scl_lv);

    gpio_set_pull_mode(sda_pin, GPIO_FLOATING);
    gpio_set_pull_mode(scl_pin, GPIO_FLOATING);
}

static void capture_frame(int frame_num) {
    ESP_LOGI(TAG, "Capturing frame %d...", frame_num);

    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == NULL) {
        ESP_LOGE(TAG, "Frame capture failed");
        return;
    }

    ESP_LOGI(TAG, "Frame %d captured:", frame_num);
    ESP_LOGI(TAG, "  Size:   %zu bytes", fb->len);
    ESP_LOGI(TAG, "  Width:  %d px", fb->width);
    ESP_LOGI(TAG, "  Height: %d px", fb->height);
    ESP_LOGI(TAG, "  Format: %d (3=JPEG)", fb->format);

    if (fb->len >= 3) {
        ESP_LOGI(TAG, "  Header: %02X %02X %02X (expect FF D8 FF for JPEG)",
                 fb->buf[0], fb->buf[1], fb->buf[2]);

        if (fb->buf[0] == 0xFF && fb->buf[1] == 0xD8 && fb->buf[2] == 0xFF) {
            ESP_LOGI(TAG, "  JPEG header: VALID");
        } else {
            ESP_LOGW(TAG, "  JPEG header: INVALID — check camera config");
        }
    }

    if (sd_mounted) {
        char filepath[32];
        snprintf(filepath, sizeof(filepath), "/sdcard/frame_%04d.jpg", frame_num);

        FILE *f = fopen(filepath, "wb");
        if (f == NULL) {
            ESP_LOGE(TAG, "Could not open %s for writing", filepath);
        } else {
            size_t written = fwrite(fb->buf, 1, fb->len, f);
            fclose(f);
            if (written == fb->len) {
                ESP_LOGI(TAG, "  Saved to %s (%zu bytes)", filepath, written);
            } else {
                ESP_LOGE(TAG, "  Write incomplete: %zu / %zu bytes", written, fb->len);
            }
        }
    } else {
        ESP_LOGW(TAG, "  SD not mounted — frame not saved");
    }

    esp_camera_fb_return(fb);
}

void app_main(void) {
    ESP_LOGI(TAG, "SmartDB ESP32-CAM basic test starting...");
    ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());
    if (ENABLE_AP) {
        wifi_init_softap();
    } else {
        ESP_LOGI(TAG, "Skipping WiFi SoftAP (ENABLE_AP=0)");
    }

    if (ENABLE_SD) {
        if (sd_init() != ESP_OK) {
            ESP_LOGW(TAG, "SD init failed or not present; continuing without SD");
        }
    } else {
        ESP_LOGI(TAG, "Skipping SD init (ENABLE_SD=0)");
    }

    gpio_level_check(CAM_PIN_SIOD, CAM_PIN_SIOC);
    sccb_debug_scan();
    /* SCCB scan above covers 0x03..0x77 addresses */

    esp_err_t cam_ret = camera_init();
    if (cam_ret != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed — halting");
        return;
    }

    ESP_LOGI(TAG, "Free heap after init: %lu bytes", esp_get_free_heap_size());
    ESP_LOGI(TAG, "Starting capture loop (10 frames, 2s interval)...");

    for (int i = 0; i < 10; i++) {
        capture_frame(i);
        vTaskDelay(pdMS_TO_TICKS(2000));
    }

    ESP_LOGI(TAG, "Test complete — %d frames captured", 10);

    if (sd_mounted) {
        esp_vfs_fat_sdcard_unmount("/sdcard", sd_card);
        ESP_LOGI(TAG, "SD card unmounted");
    }
}
