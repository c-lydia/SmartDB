#pragma once
#include "fusion_core.h"
/* No physical alignment is assumed. Replace using tools/calibrate.py. */
static const fc_calibration_t installation_calibration = {
    .enabled = false, .version = "uncalibrated", .width = 320, .height = 240,
    .rgb_to_thermal = {1,0,0, 0,1,0, 0,0,1},
    .display_min_c = 20, .display_max_c = 80, .opacity = 0.45f,
};
/* Edit regions to match the registered installation, then rebuild. */
static const fc_region_t installation_regions[] = {
    {"panel", 0, 0, 319, 239, 4},
};
