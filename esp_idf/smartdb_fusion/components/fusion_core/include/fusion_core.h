#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define FC_TW 32
#define FC_TH 24
#define FC_PIXELS (FC_TW * FC_TH)
#define FC_MAX_REGIONS 8

typedef struct {
    float celsius[FC_PIXELS];
    uint8_t valid[FC_PIXELS], corrected[FC_PIXELS];
    int64_t start_us, end_us;
    uint32_t sequence;
} fc_thermal_t;

typedef struct {
    bool enabled;
    const char *version;
    unsigned width, height;
    /* RGB pixel centres -> native thermal pixel centres, row-major. */
    float rgb_to_thermal[9];
    float display_min_c, display_max_c, opacity;
} fc_calibration_t;

typedef struct {
    const char *id;
    float x0, y0, x1, y1; /* RGB pixel-centre coordinates. */
    unsigned min_samples;
} fc_region_t;

typedef struct {
    unsigned samples, boundary_samples;
    bool supported, ambiguous;
    float max_c, mean_c;
} fc_measurement_t;

bool fc_calibration_valid(const fc_calibration_t *cal);
bool fc_pair_valid(
    const fc_thermal_t *t,
    int64_t rgb_start,
    int64_t rgb_end,
    int64_t now,
    int64_t max_span,
    int64_t max_age
);
/* Out-of-coverage or invalid neighbourhood returns false; no extrapolation. */
bool fc_bicubic(const fc_thermal_t *t, float x, float y, float *celsius);
bool fc_render(
    const fc_calibration_t *cal,
    const fc_thermal_t *thermal,
    const uint8_t *rgb,
    uint8_t *fused,
    size_t buffer_size
);
bool fc_measure(
    const fc_calibration_t *cal,
    const fc_thermal_t *thermal,
    const fc_region_t *regions,
    size_t count,
    fc_measurement_t *out
);
void fc_demo(fc_thermal_t *thermal, uint8_t *rgb, unsigned width, unsigned height, int64_t now);
/* RGB888 to top-down 24-bit BMP; caller supplies full output buffer. */
size_t fc_bmp_size(unsigned width, unsigned height);
bool fc_bmp(const uint8_t *rgb, unsigned width, unsigned height, uint8_t *out, size_t size);
