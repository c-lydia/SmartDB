#include "protection.h"
#include <math.h>
void pc_rms_add(pc_rms_t *w,int16_t code) {
    if(code>32000||code< -32000) {w->invalid=true;return;}
    double volts=code*(.256/32768.0),delta=volts-w->mean;
    w->count++;w->mean+=delta/w->count;w->m2+=delta*(volts-w->mean);
}
float pc_rms_current(const pc_rms_t *w,float scale) {
    if(w->invalid||w->count<32||!isfinite(scale)||scale<=0) return NAN;
    return sqrt(w->m2/w->count)*scale;
}
bool pc_config_valid(const pc_config_t *c) {
    return c&&c->version>0&&isfinite(c->current_limit_a)&&c->current_limit_a>0&&c->current_limit_a<=1
        &&isfinite(c->temperature_limit_c)&&c->temperature_limit_c>=20&&c->temperature_limit_c<=100
        &&isfinite(c->current_scale_a_per_v)&&c->current_scale_a_per_v>=50&&c->current_scale_a_per_v<=200;
}
void pc_init(pc_controller_t *p,bool trip) {
    *p=(pc_controller_t){.state=trip?PC_TRIPPED:PC_DISARMED,.reason=trip?PC_MANUAL:PC_NOT_CONFIGURED,.healthy_since_us=-1};
}
bool pc_update(pc_controller_t *p,const pc_config_t *c,const pc_input_t *in,int64_t now,bool rearm,bool open) {
    pc_state_t before=p->state;pc_reason_t reason=p->reason;
    bool configured=pc_config_valid(c)&&c->commissioned;
    bool sensors=in&&in->current_valid&&in->thermal_valid&&isfinite(in->current_a)&&in->current_a>=0
        &&isfinite(in->temperature_c)&&in->current_time_us>=0&&in->thermal_time_us>=0
        &&in->current_time_us<=now&&in->thermal_time_us<=now
        &&now-in->current_time_us<=500000&&now-in->thermal_time_us<=1500000;
    pc_reason_t fault=!configured?PC_NOT_CONFIGURED:!sensors?PC_SENSOR_FAULT:
        in->current_a>=c->current_limit_a?PC_OVERCURRENT:in->temperature_c>=c->temperature_limit_c?PC_OVERHEAT:PC_NONE;
    bool cool=fault==PC_NONE&&in->current_a<c->current_limit_a*.9f&&in->temperature_c<c->temperature_limit_c-5;
    if(!cool) p->healthy_since_us=-1;
    else if(p->healthy_since_us<0) p->healthy_since_us=now;
    if(p->state==PC_ARMED&&fault!=PC_NONE) {p->state=PC_TRIPPED;p->reason=fault;}
    else if(open&&p->state!=PC_TRIPPED) {p->state=PC_DISARMED;p->reason=PC_MANUAL;}
    else if(rearm&&!open&&p->state!=PC_ARMED&&cool&&now-p->healthy_since_us>=2000000) {p->state=PC_ARMED;p->reason=PC_NONE;}
    else if(p->state==PC_DISARMED&&fault!=PC_NONE) p->reason=fault;
    return p->state!=before||p->reason!=reason;
}
const char *pc_state_name(pc_state_t s) {
    switch(s) {case PC_ARMED:return "armed";case PC_TRIPPED:return "tripped";default:return "disarmed";}
}
const char *pc_reason_name(pc_reason_t r) {
    switch(r) {case PC_NONE:return "none";case PC_NOT_CONFIGURED:return "not_commissioned";
        case PC_SENSOR_FAULT:return "sensor_fault_or_stale";case PC_OVERCURRENT:return "overcurrent";
        case PC_OVERHEAT:return "overheat";case PC_STORAGE_FAULT:return "storage_fault";default:return "manual";}
}
