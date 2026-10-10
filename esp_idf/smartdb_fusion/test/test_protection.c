#include "protection.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
static pc_config_t config={1,true,.8f,60,2000.0f/18};
static pc_input_t sample(int64_t now,float current,float temp) {
    return (pc_input_t){true,true,current,temp,now,now};
}
static void arm(pc_controller_t *p,int64_t now) {
    pc_input_t in=sample(now,.2f,30);
    pc_update(p,&config,&in,now,false,false);in=sample(now+2000001,.2f,30);
    pc_update(p,&config,&in,now+2000001,true,false);assert(p->state==PC_ARMED);
}
int main(void) {
    pc_rms_t rms={0};
    assert(isnan(pc_rms_current(&rms,2000.0f/18)));
    /* Ten 50 Hz cycles at 400 samples/s; a DC bias must not become AC current. */
    for(int i=0;i<80;i++) pc_rms_add(&rms,(int16_t)lround(123+(.5*sqrt(2)/(2000.0/18))/(.256/32768)*sin(2*3.141592653589793*i/8)));
    assert(fabsf(pc_rms_current(&rms,2000.0f/18)-.5f)<.001f);
    pc_rms_add(&rms,32767);assert(isnan(pc_rms_current(&rms,2000.0f/18)));
    rms=(pc_rms_t){0};for(int i=0;i<80;i++) pc_rms_add(&rms,100);
    assert(pc_rms_current(&rms,2000.0f/18)==0);
    pc_controller_t p;pc_init(&p,false);assert(p.state==PC_DISARMED);
    pc_input_t in=sample(100,.2f,30);
    pc_update(&p,&config,&in,100,true,false);assert(p.state==PC_DISARMED);
    arm(&p,100);in=sample(2100000,.81f,30);
    pc_update(&p,&config,&in,2100000,false,false);assert(p.state==PC_TRIPPED&&p.reason==PC_OVERCURRENT);
    in=sample(2200000,.1f,30);pc_update(&p,&config,&in,2200000,false,true);assert(p.state==PC_TRIPPED);
    arm(&p,2300000);in=sample(4500000,.1f,61);
    pc_update(&p,&config,&in,4500000,false,false);assert(p.state==PC_TRIPPED&&p.reason==PC_OVERHEAT);
    pc_init(&p,true);assert(p.state==PC_TRIPPED);
    in=sample(4600000,.1f,30);pc_update(&p,&config,&in,4600000,false,false);
    in=sample(6700000,.1f,30);pc_update(&p,&config,&in,6700000,true,true);
    assert(p.state==PC_TRIPPED); /* An open request wins a simultaneous physical re-arm. */
    pc_init(&p,true);arm(&p,5000000);
    in=sample(7200000,.1f,30);in.current_valid=false;
    pc_update(&p,&config,&in,7200000,false,false);assert(p.state==PC_TRIPPED&&p.reason==PC_SENSOR_FAULT);
    arm(&p,7300000);in=sample(9500000,.1f,30);in.current_time_us=8000000;
    pc_update(&p,&config,&in,9500000,false,false);assert(p.state==PC_TRIPPED);
    arm(&p,9600000);in=sample(12000000,NAN,30);
    pc_update(&p,&config,&in,12000000,false,false);assert(p.state==PC_TRIPPED);
    arm(&p,13000000);in=sample(15100000,.1f,30);pc_update(&p,&config,&in,15100000,false,true);assert(p.state==PC_DISARMED);
    config.commissioned=false;in=sample(18000000,.1f,30);pc_update(&p,&config,&in,18000000,true,false);assert(p.state==PC_DISARMED);
    config.current_limit_a=5;assert(!pc_config_valid(&config));
    puts("Protection tests passed: startup, physical re-arm, overload, heat, stale/invalid data, persistent latch, remote-open-only.");
}
