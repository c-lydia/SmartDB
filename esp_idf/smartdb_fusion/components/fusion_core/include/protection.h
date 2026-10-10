#pragma once
#include <stdbool.h>
#include <stdint.h>
typedef enum {PC_DISARMED, PC_ARMED, PC_TRIPPED} pc_state_t;
typedef enum {PC_NONE, PC_NOT_CONFIGURED, PC_SENSOR_FAULT, PC_OVERCURRENT, PC_OVERHEAT, PC_MANUAL, PC_STORAGE_FAULT} pc_reason_t;
typedef struct {
    uint32_t version;
    bool commissioned;
    float current_limit_a, temperature_limit_c, current_scale_a_per_v;
} pc_config_t;
typedef struct {
    bool current_valid, thermal_valid;
    float current_a, temperature_c;
    int64_t current_time_us, thermal_time_us;
} pc_input_t;
typedef struct {
    pc_state_t state;
    pc_reason_t reason;
    int64_t healthy_since_us;
} pc_controller_t;
bool pc_config_valid(const pc_config_t *c);
void pc_init(pc_controller_t *p,bool persisted_trip);
/* All times use the same local monotonic clock. No network input can arm. */
bool pc_update(pc_controller_t *p,const pc_config_t *c,const pc_input_t *in,int64_t now,bool physical_rearm,bool open_request);
const char *pc_state_name(pc_state_t state);
const char *pc_reason_name(pc_reason_t reason);
typedef struct {unsigned count;double mean,m2;bool invalid;} pc_rms_t;
void pc_rms_add(pc_rms_t *window,int16_t adc_code);
float pc_rms_current(const pc_rms_t *window,float scale_a_per_v);
