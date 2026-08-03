/**
 * ESP32-CAM Basic Test
 * AI Thinker ESP32-CAM with OV2640
 *
 * Tests:
 *  1. Camera initialisation
 *  2. Frame capture
 *  3. Frame metadata logging (size, resolution, format)
 *  4. SD card mount + save JPEG
 *
 * Wiring (AI Thinker ESP32-CAM):
 *  - Use FTDI programmer for flashing (no USB on ESP32-CAM)
 *  - GPIO0 to GND during flash, disconnect after
 *  - FTDI TX → ESP32-CAM U0R (GPIO3)
 *  - FTDI RX → ESP32-CAM U0T (GPIO1)
 *  - FTDI 5V → ESP32-CAM 5V
 *  - FTDI GND → ESP32-CAM GND
 */

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_camera.h"

/* Minimal SCCB prototypes to avoid including private component headers */
extern int SCCB_Init(int pin_sda, int pin_scl);
extern uint8_t SCCB_Read16(uint8_t slv_addr, uint16_t reg);
extern int SCCB_Probe(uint8_t slv_addr);
#include "esp_vfs_fat.h"
#include "driver/sdmmc_host.h"
#include "sdmmc_cmd.h"

static const char *TAG = "esp32cam_test";

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
    .fb_count     = 2,                  // 2 frame buffers (double buffering)
    .fb_location  = CAMERA_FB_IN_PSRAM, // use PSRAM for frame buffers
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

static void sccb_debug_scan(void) {
    ESP_LOGI(TAG, "Starting SCCB debug scan (this may take a few seconds)...");
    SCCB_Init(CAM_PIN_SIOD, CAM_PIN_SIOC);
    for (int addr = 0x20; addr <= 0x7E; addr++) {
        int h = SCCB_Read16(addr, 0x300A);
        int l = SCCB_Read16(addr, 0x300B);
        if (h >= 0 && l >= 0) {
            uint16_t pid = ((uint16_t)h << 8) | (uint16_t)l;
            ESP_LOGI(TAG, "SCCB addr=0x%02x -> PID=0x%04x (h=0x%02x l=0x%02x)", addr, pid, h & 0xff, l & 0xff);
        }
    }
    ESP_LOGI(TAG, "SCCB debug scan complete");
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
    // OV2640 PID = 0x26, OV5640 PID = 0x56

    // optional sensor adjustments
    s->set_brightness(s, 0);    // -2 to 2
    s->set_contrast(s, 0);      // -2 to 2
    s->set_saturation(s, 0);    // -2 to 2
    s->set_whitebal(s, 1);      // auto white balance on
    s->set_exposure_ctrl(s, 1); // auto exposure on

    ESP_LOGI(TAG, "Camera initialised successfully");
    return ESP_OK;
}

static void capture_frame(int frame_num) {
    ESP_LOGI(TAG, "Capturing frame %d...", frame_num);

    camera_fb_t *fb = esp_camera_fb_get();
    if (fb == NULL) {
        ESP_LOGE(TAG, "Frame capture failed");
        return;
    }

    // log frame metadata
    ESP_LOGI(TAG, "Frame %d captured:", frame_num);
    ESP_LOGI(TAG, "  Size:   %zu bytes", fb->len);
    ESP_LOGI(TAG, "  Width:  %d px", fb->width);
    ESP_LOGI(TAG, "  Height: %d px", fb->height);
    ESP_LOGI(TAG, "  Format: %d (3=JPEG)", fb->format);

    // log first 16 bytes of JPEG header for sanity check
    // valid JPEG starts with FF D8 FF
    if (fb->len >= 3) {
        ESP_LOGI(TAG, "  Header: %02X %02X %02X (expect FF D8 FF for JPEG)",
                 fb->buf[0], fb->buf[1], fb->buf[2]);

        if (fb->buf[0] == 0xFF && fb->buf[1] == 0xD8 && fb->buf[2] == 0xFF) {
            ESP_LOGI(TAG, "  JPEG header: VALID");
        } else {
            ESP_LOGW(TAG, "  JPEG header: INVALID — check camera config");
        }
    }

    // save to SD card if mounted
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

    // return frame buffer to camera driver — MUST do this or camera stalls
    esp_camera_fb_return(fb);
}

void app_main(void) {
    ESP_LOGI(TAG, "SmartDB ESP32-CAM basic test starting...");
    ESP_LOGI(TAG, "Free heap: %lu bytes", esp_get_free_heap_size());

    // init SD card (optional — camera test works without it)
    esp_err_t sd_ret = sd_init();
    if (sd_ret != ESP_OK) {
        ESP_LOGW(TAG, "SD card not available — continuing without SD");
    }

    sccb_debug_scan();

    // init camera
    esp_err_t cam_ret = camera_init();
    if (cam_ret != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed — halting");
        return;
    }

    ESP_LOGI(TAG, "Free heap after init: %lu bytes", esp_get_free_heap_size());
    ESP_LOGI(TAG, "Starting capture loop (10 frames, 2s interval)...");

    // capture 10 frames, 2 seconds apart
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