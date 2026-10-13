#include "fusion_core.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static fc_thermal_t thermal;
static uint8_t rgb[320 * 240 * 3], fused[320 * 240 * 3];
static fc_calibration_t cal = {
    true, "fixture", 320, 240, {31.0f / 319, 0, 0, 0, 23.0f / 239, 0, 0, 0, 1}, 20, 80, .45f
};

static void reset(void) {
    fc_demo(&thermal, rgb, 320, 240, 1000000);
    thermal.start_us = 900000;
    thermal.end_us = 1000000;
}

int main(int argc, char **argv) {
    reset();
    assert(fc_calibration_valid(&cal));
    fc_calibration_t bad = cal;
    bad.enabled = false;
    assert(!fc_calibration_valid(&bad));
    bad = cal;
    bad.rgb_to_thermal[0] = 0;
    assert(!fc_calibration_valid(&bad));
    bad = cal;
    bad.rgb_to_thermal[6] = -.01f;
    assert(!fc_calibration_valid(&bad));
    bad = cal;
    bad.opacity = NAN;
    assert(!fc_calibration_valid(&bad));
    assert(fc_pair_valid(&thermal, 1000000, 1100000, 1200000, 500000, 2000000));
    assert(!fc_pair_valid(&thermal, 1000000, 1100000, 4000000, 500000, 2000000));
    assert(!fc_pair_valid(&thermal, 2000000, 2100000, 2200000, 500000, 2000000));
    assert(!fc_pair_valid(&thermal, 1000000, 1300000, 1200000, 500000, 2000000));
    assert(!fc_pair_valid(&thermal, -1, 1100000, 1200000, 500000, 2000000));
    thermal.end_us = 800000;
    assert(!fc_pair_valid(&thermal, 1000000, 1100000, 1200000, 500000, 2000000));
    reset();
    float t;
    assert(fc_bicubic(&thermal, 20, 12, &t) && fabsf(t - 70) < .001f);
    assert(!fc_bicubic(&thermal, -.001f, 0, &t));
    assert(!fc_bicubic(&thermal, INFINITY, 0, &t));
    thermal.valid[12 * 32 + 20] = 0;
    assert(!fc_bicubic(&thermal, 20, 12, &t));
    thermal.valid[12 * 32 + 20] = 1;
    thermal.corrected[12 * 32 + 20] = 1;
    assert(!fc_bicubic(&thermal, 20, 12, &t));
    reset();
    /* Step signal exposes cubic overshoot: display result stays within measured limits. */
    for (int y = 0; y < 24; y++) {
        for (int x = 0; x < 32; x++) {
            thermal.celsius[y * 32 + x] = x < 16 ? 20 : 80;
        }
    }

    for (float x = 12; x < 20; x += .05f) {
        assert(fc_bicubic(&thermal, x, 12.3f, &t));
        assert(t >= 20 && t <= 80);
    }

    reset();
    assert(fc_render(&cal, &thermal, rgb, fused, sizeof(fused)));
    assert(memcmp(rgb, fused, sizeof(rgb)) != 0);
    assert(!fc_render(&cal, &thermal, rgb, fused, 2));
    bad = cal;
    bad.rgb_to_thermal[2] = 50;
    assert(fc_render(&bad, &thermal, rgb, fused, sizeof(fused)));
    assert(!memcmp(rgb, fused, sizeof(rgb)));
    fc_region_t r[] = {{"panel", 0, 0, 319, 239, 4}, {"overlap", 100, 50, 250, 200, 4}};
    fc_measurement_t m[2];
    assert(fc_measure(&cal, &thermal, r, 1, m));
    assert(m[0].supported && m[0].samples == 30 * 22 && fabsf(m[0].max_c - 70) < .001f);
    thermal.corrected[12 * 32 + 20] = 1;
    assert(fc_measure(&cal, &thermal, r, 1, m));
    assert(m[0].max_c < 70);
    reset();
    assert(fc_measure(&cal, &thermal, r, 2, m));
    assert(m[0].ambiguous && m[1].ambiguous && !m[0].supported && isnan(m[0].max_c));
    fc_region_t tiny = {"tiny", 201, 119, 207, 125, 4};
    assert(fc_measure(&cal, &thermal, &tiny, 1, m));
    assert(!m[0].supported && isnan(m[0].max_c));
    fc_region_t invalid = {"bad", 0, 0, 400, 239, 4};
    assert(!fc_measure(&cal, &thermal, &invalid, 1, m));
    /* Translation maps RGB region [110,210] onto thermal x=[10,20] rather than [11,21]. */
    fc_calibration_t translated = cal;
    float h[9] = {.1f, 0, -1, 0, .1f, 0, 0, 0, 1};
    memcpy(translated.rgb_to_thermal, h, sizeof(h));
    fc_region_t region = {"translated", 110, 50, 210, 150, 4};

    for (int y = 0; y < 24; y++) {
        for (int x = 0; x < 32; x++) {
            thermal.celsius[y * 32 + x] = (float)x;
        }
    }

    assert(fc_measure(&translated, &thermal, &region, 1, m));
    assert(m[0].supported && m[0].max_c == 19);
    uint8_t px[6] = {255, 0, 0, 0, 0, 255}, bmp[62];
    assert(fc_bmp_size(2, 1) == 62);
    assert(fc_bmp(px, 2, 1, bmp, sizeof(bmp)));
    assert(bmp[54] == 0 && bmp[56] == 255 && bmp[57] == 255 && bmp[59] == 0);
    assert(bmp[22] == 255 && bmp[23] == 255 && bmp[24] == 255 && bmp[25] == 255);
    assert(!fc_bmp(px, 2, 1, bmp, 61));

    if (argc == 2) {
        reset();
        assert(fc_render(&cal, &thermal, rgb, fused, sizeof(fused)));
        size_t size = fc_bmp_size(320, 240);
        uint8_t *b = malloc(size);
        assert(b);
        assert(fc_bmp(fused, 320, 240, b, size));
        FILE *f = fopen(argv[1], "wb");
        assert(f);
        assert(fwrite(b, 1, size, f) == size);
        fclose(f);
        free(b);
    }

    puts(
        "Fusion tests passed: timing, invalid data, transforms, native measurements, ambiguity, "
        "cubic bounds, BMP."
    );
}
