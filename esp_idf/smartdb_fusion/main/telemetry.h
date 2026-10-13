#pragma once
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
typedef char *(*telemetry_snapshot_fn)(void); /* Returns malloc-owned JSON. */

typedef struct {
    uint8_t *bytes;
    size_t size;
    uint32_t sequence, age_ms;
    bool synthetic;
} telemetry_frame_t;

/* Returns a free()-owned copy only when the local fusion is fresh. */
typedef telemetry_frame_t (*telemetry_frame_fn)(void);
void telemetry_start(telemetry_snapshot_fn snapshot, telemetry_frame_fn frame);
