#include "thermal_sensor.h"
#include "project_config.h"
#include "MLX90640_API.h"
#include "MLX90640_I2C_Driver.h"
#include "driver/i2c_master.h"
#include "sensor_bus.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <math.h>
#include <string.h>
static i2c_master_dev_handle_t sensor;
static paramsMLX90640 params;
static int64_t deadline;
static uint32_t sequence;
void MLX90640_I2CInit(void) {}
void MLX90640_I2CFreqSet(int freq) {(void)freq;}
int MLX90640_I2CGeneralReset(void) {return -1;} /* Never reset the shared ADS1115 bus. */
int MLX90640_I2CRead(uint8_t address,uint16_t reg,uint16_t count,uint16_t *data) {
    if(address!=0x33||!sensor||!data) return -1;
    while(count) {
        if(esp_timer_get_time()>deadline) return -1;
        uint16_t n=count>16?16:count;
        uint8_t cmd[2]={(uint8_t)(reg>>8),(uint8_t)reg},bytes[128];
        if(i2c_master_transmit_receive(sensor,cmd,2,bytes,n*2,50)!=ESP_OK) return -1;
        for(unsigned i=0;i<n;i++) data[i]=((uint16_t)bytes[2*i]<<8)|bytes[2*i+1];
        if(reg==0x8000 && !(data[0]&8)) vTaskDelay(pdMS_TO_TICKS(2));
        reg+=n;count-=n;data+=n;
    }
    return 0;
}
int MLX90640_I2CWrite(uint8_t address,uint16_t reg,uint16_t value) {
    if(address!=0x33||!sensor||esp_timer_get_time()>deadline) return -1;
    uint8_t cmd[4]={(uint8_t)(reg>>8),(uint8_t)reg,(uint8_t)(value>>8),(uint8_t)value};
    return i2c_master_transmit(sensor,cmd,4,50)==ESP_OK?0:-1;
}
esp_err_t thermal_init(void) {
    if(!isfinite(SMARTDB_EMISSIVITY)||SMARTDB_EMISSIVITY<=0||SMARTDB_EMISSIVITY>1||!isfinite(SMARTDB_REFLECTED_OFFSET_C)) return ESP_ERR_INVALID_ARG;
    esp_err_t err=sensor_bus_device(0x33,&sensor);if(err!=ESP_OK) return err;
    uint16_t eeprom[832];deadline=esp_timer_get_time()+2000000;
    if(MLX90640_DumpEE(0x33,eeprom)!=0 || MLX90640_ExtractParameters(eeprom,&params)!=0
       || MLX90640_SetChessMode(0x33)!=0 || MLX90640_SetRefreshRate(0x33,4)!=0) return ESP_FAIL;
    return ESP_OK;
}
esp_err_t thermal_capture(fc_thermal_t *out) {
    static uint16_t frame[834];
    memset(out,0,sizeof(*out));for(int i=0;i<FC_PIXELS;i++) out->celsius[i]=NAN;
    out->start_us=esp_timer_get_time();deadline=out->start_us+750000;
    /* Clear pending-ready state so both subpages belong to this capture window. */
    if(MLX90640_I2CWrite(0x33,0x8000,0x0030)!=0) return ESP_FAIL;
    unsigned pages=0;
    for(int tries=0;tries<6 && pages!=3;tries++) {
        int page=MLX90640_GetFrameData(0x33,frame);
        if(page<0||page>1) return ESP_FAIL;
        float ta=MLX90640_GetTa(frame,&params);
        if(!isfinite(ta)) return ESP_FAIL;
        MLX90640_CalculateTo(frame,&params,SMARTDB_EMISSIVITY,ta-SMARTDB_REFLECTED_OFFSET_C,out->celsius);
        pages|=1u<<page;
    }
    if(pages!=3) return ESP_ERR_TIMEOUT;
    out->end_us=esp_timer_get_time();out->sequence=++sequence;
    for(int i=0;i<FC_PIXELS;i++) out->valid[i]=isfinite(out->celsius[i]);
    /* Exclude factory-bad pixels instead of inventing measured temperatures. */
    for(int k=0;k<5;k++) {
        if(params.brokenPixels[k]<FC_PIXELS) out->valid[params.brokenPixels[k]]=0;
        if(params.outlierPixels[k]<FC_PIXELS) out->valid[params.outlierPixels[k]]=0;
    }
    return ESP_OK;
}
