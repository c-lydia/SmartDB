#include "system_control.h"
#include "project_config.h"
#include "protection.h"
#include "sensor_bus.h"
#include "thermal_sensor.h"
#include "network.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "esp_log.h"
#include "esp_task_wdt.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/queue.h"
#include <math.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <limits.h>

typedef struct {uint32_t sequence,boot;int64_t uptime_us;pc_state_t state;pc_reason_t reason;float current_a,temperature_c;} event_t;
static SemaphoreHandle_t mutex;
static QueueHandle_t event_queue;
static nvs_handle_t storage;
static pc_config_t config={.version=1,.commissioned=false,.current_limit_a=.8f,.temperature_limit_c=60,.current_scale_a_per_v=2000.0f/18};
static pc_controller_t controller;
static pc_input_t input={.current_a=NAN,.temperature_c=NAN};
static fc_thermal_t latest_thermal;
static bool open_requested,storage_ok=true;
static uint32_t boot_id,event_sequence;
static event_t history[16];
static unsigned history_count;
static i2c_master_dev_handle_t adc;

static void persist_task(void *arg) {
    (void)arg;event_t event;
    while(xQueueReceive(event_queue,&event,portMAX_DELAY)==pdTRUE) {
        event_t copy[16];unsigned count;
        xSemaphoreTake(mutex,portMAX_DELAY);
        if(history_count==16) {memmove(history,history+1,15*sizeof(event_t));history_count--;}
        history[history_count++]=event;count=history_count;memcpy(copy,history,count*sizeof(event_t));xSemaphoreGive(mutex);
        esp_err_t e=nvs_set_blob(storage,"events",copy,count*sizeof(event_t));
        if(e==ESP_OK) e=nvs_set_u32(storage,"event_seq",event.sequence);
        if(e==ESP_OK) e=nvs_set_u8(storage,"trip",event.state==PC_TRIPPED);
        if(e==ESP_OK) e=nvs_commit(storage);
        if(e!=ESP_OK) {xSemaphoreTake(mutex,portMAX_DELAY);storage_ok=false;xSemaphoreGive(mutex);}
    }
}
static void outputs(int64_t now) {
    bool armed=controller.state==PC_ARMED && !SMARTDB_DEMO;
    gpio_set_level(4,armed);
    bool trip=controller.state==PC_TRIPPED;
    gpio_set_level(6,trip);gpio_set_level(7,armed);gpio_set_level(8,!armed&&!trip);
    /* The PCB buzzer type is unresolved; keep drive off unless explicitly selected as active. */
#if SMARTDB_ACTIVE_BUZZER
    gpio_set_level(5,trip&&((now/250000)%4==0));
#else
    (void)now;gpio_set_level(5,0);
#endif
}
static void protection_task(void *arg) {
    (void)arg;TickType_t last=xTaskGetTickCount();bool released=false;int64_t pressed=-1;
    ESP_ERROR_CHECK(esp_task_wdt_add(NULL));
    for(;;) {
        int64_t now=esp_timer_get_time();bool rearm=false,local_open=false;
        if(gpio_get_level(0)) {
            if(pressed>=0 && now-pressed>=2000000) {rearm=true;local_open=true;}
            pressed=-1;released=true;
        } else if(released&&pressed<0) pressed=now;
        xSemaphoreTake(mutex,portMAX_DELAY);
        pc_state_t before=controller.state;
        bool open=open_requested||(local_open&&before==PC_ARMED);open_requested=false;
        if(SMARTDB_DEMO) {config.commissioned=false;rearm=false;}
        pc_update(&controller,&config,&input,now,rearm,open);
        if(!storage_ok) {controller.state=PC_TRIPPED;controller.reason=PC_STORAGE_FAULT;}
        outputs(now); /* GPIO cutoff happens before event persistence or network activity. */
        bool changed=before!=controller.state;
        event_t event={0};
        if(changed) {
            if(event_sequence==UINT32_MAX) {storage_ok=false;gpio_set_level(4,0);}
            else event=(event_t){++event_sequence,boot_id,now,controller.state,controller.reason,input.current_a,input.temperature_c};
        }
        xSemaphoreGive(mutex);
        if(changed && xQueueSend(event_queue,&event,0)!=pdTRUE) {
            gpio_set_level(4,0);xSemaphoreTake(mutex,portMAX_DELAY);storage_ok=false;xSemaphoreGive(mutex);
        }
        ESP_ERROR_CHECK(esp_task_wdt_reset());
        vTaskDelayUntil(&last,pdMS_TO_TICKS(10));
    }
}
static esp_err_t adc_read(uint8_t reg,uint16_t *value) {
    uint8_t data[2];esp_err_t e=i2c_master_transmit_receive(adc,&reg,1,data,2,20);
    if(e==ESP_OK) *value=((uint16_t)data[0]<<8)|data[1];
    return e;
}
static void current_task(void *arg) {
    (void)arg;
    if(sensor_bus_device(0x48,&adc)!=ESP_OK) {vTaskDelete(NULL);return;}
    for(;;) {
        xSemaphoreTake(mutex,portMAX_DELAY);pc_config_t cfg=config;xSemaphoreGive(mutex);
        pc_rms_t rms={0};bool good=true;
        int64_t start=esp_timer_get_time(),previous=start;
        while(esp_timer_get_time()-start<200000) {
            /* ADS1115: differential AIN0-AIN1, +/-0.256 V, single shot, 860 SPS, comparator off. */
            uint8_t command[3]={1,0x8b,0xe3};
            if(i2c_master_transmit(adc,command,3,20)!=ESP_OK) {good=false;break;}
            int64_t conversion_start=esp_timer_get_time();uint16_t status=0,raw=0;
            do {
                vTaskDelay(pdMS_TO_TICKS(2));
                if(adc_read(1,&status)!=ESP_OK) {good=false;break;}
            } while(!(status&0x8000)&&esp_timer_get_time()-conversion_start<15000);
            if(!good||!(status&0x8000)||adc_read(0,&raw)!=ESP_OK) {good=false;break;}
            int64_t now=esp_timer_get_time();
            int16_t code=(int16_t)raw;
            pc_rms_add(&rms,code);
            if(rms.invalid||now-previous>20000) {good=false;break;}
            previous=now;
        }
        xSemaphoreTake(mutex,portMAX_DELAY);
        float amperes=pc_rms_current(&rms,cfg.current_scale_a_per_v);
        input.current_valid=good&&isfinite(amperes)&&config.version==cfg.version;
        input.current_time_us=esp_timer_get_time();
        input.current_a=input.current_valid?amperes:NAN;
        xSemaphoreGive(mutex);if(!good) vTaskDelay(pdMS_TO_TICKS(50));
    }
}
static void thermal_task(void *arg) {
    (void)arg;
    if(thermal_init()!=ESP_OK) {ESP_LOGE("sensing","MLX initialization failed");vTaskDelete(NULL);return;}
    static fc_thermal_t frame;
    for(;;) {
        bool good=thermal_capture(&frame)==ESP_OK;float max=-INFINITY;unsigned count=0;
        if(good) for(int i=0;i<FC_PIXELS;i++) if(frame.valid[i]&&!frame.corrected[i]&&isfinite(frame.celsius[i])) {max=fmaxf(max,frame.celsius[i]);count++;}
        xSemaphoreTake(mutex,portMAX_DELAY);
        input.thermal_valid=good&&count>=760;input.thermal_time_us=good?frame.start_us:esp_timer_get_time();
        input.temperature_c=input.thermal_valid?max:NAN;
        if(input.thermal_valid) latest_thermal=frame;
        xSemaphoreGive(mutex);vTaskDelay(pdMS_TO_TICKS(100));
    }
}
esp_err_t system_start(void) {
    gpio_config_t pins={.pin_bit_mask=(1ULL<<4)|(1ULL<<5)|(1ULL<<6)|(1ULL<<7)|(1ULL<<8),.mode=GPIO_MODE_OUTPUT};
    gpio_set_level(4,0);ESP_ERROR_CHECK(gpio_config(&pins));gpio_set_level(4,0);
    gpio_config_t button={.pin_bit_mask=1,.mode=GPIO_MODE_INPUT,.pull_up_en=GPIO_PULLUP_ENABLE};ESP_ERROR_CHECK(gpio_config(&button));
    esp_err_t e=nvs_flash_init();if(e!=ESP_OK) return e;
    e=nvs_open("smartdb",NVS_READWRITE,&storage);if(e!=ESP_OK) return e;
    pc_config_t saved;size_t size=sizeof(saved);e=nvs_get_blob(storage,"config",&saved,&size);
    if(e==ESP_OK&&size==sizeof(saved)&&pc_config_valid(&saved)) config=saved;
    else if(e!=ESP_ERR_NVS_NOT_FOUND) storage_ok=false;
    uint8_t trip=0;e=nvs_get_u8(storage,"trip",&trip);if(e!=ESP_OK&&e!=ESP_ERR_NVS_NOT_FOUND) storage_ok=false;
    e=nvs_get_u32(storage,"event_seq",&event_sequence);if(e!=ESP_OK&&e!=ESP_ERR_NVS_NOT_FOUND) storage_ok=false;
    size=sizeof(history);e=nvs_get_blob(storage,"events",history,&size);
    if(e==ESP_OK&&size%sizeof(event_t)==0) history_count=size/sizeof(event_t);
    else if(e!=ESP_ERR_NVS_NOT_FOUND) storage_ok=false;
    pc_init(&controller,trip!=0);boot_id=esp_random();
    mutex=xSemaphoreCreateMutex();event_queue=xQueueCreate(8,sizeof(event_t));if(!mutex||!event_queue) return ESP_ERR_NO_MEM;
    ESP_ERROR_CHECK(sensor_bus_init());
    if(xTaskCreatePinnedToCore(protection_task,"protection",4096,NULL,15,NULL,1)!=pdPASS) return ESP_ERR_NO_MEM;
    if(xTaskCreate(persist_task,"event_store",4096,NULL,3,NULL)!=pdPASS) return ESP_ERR_NO_MEM;
    if(!SMARTDB_DEMO) {
        if(xTaskCreatePinnedToCore(current_task,"current_rms",4096,NULL,12,NULL,1)!=pdPASS) return ESP_ERR_NO_MEM;
        if(xTaskCreatePinnedToCore(thermal_task,"thermal",12288,NULL,8,NULL,1)!=pdPASS) return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}
bool system_thermal_snapshot(fc_thermal_t *out) {
    xSemaphoreTake(mutex,portMAX_DELAY);bool ok=input.thermal_valid&&esp_timer_get_time()-input.thermal_time_us<=1500000;
    if(ok) *out=latest_thermal;
    xSemaphoreGive(mutex);return ok;
}
void system_add_status(cJSON *root) {
    xSemaphoreTake(mutex,portMAX_DELAY);int64_t now=esp_timer_get_time();
    cJSON_AddNumberToObject(root,"current",input.current_valid&&now-input.current_time_us<=500000?input.current_a:NAN);
    cJSON_AddNumberToObject(root,"temperature",input.thermal_valid&&now-input.thermal_time_us<=1500000?input.temperature_c:NAN);
    cJSON_AddStringToObject(root,"relay_state",controller.state==PC_ARMED&&!SMARTDB_DEMO?"closed":"open");
    cJSON_AddStringToObject(root,"protection_state",pc_state_name(controller.state));
    cJSON_AddStringToObject(root,"protection_reason",pc_reason_name(controller.reason));
    cJSON_AddNumberToObject(root,"config_version",config.version);cJSON_AddBoolToObject(root,"commissioned",config.commissioned&&!SMARTDB_DEMO);
    cJSON_AddBoolToObject(root,"storage_ok",storage_ok);
    cJSON_AddStringToObject(root,"current_sensor","SCT-013-000 AC only; 18 ohm burden");
    cJSON_AddBoolToObject(root,"arc_detection_available",false);
    cJSON *events=cJSON_AddArrayToObject(root,"events");
    for(unsigned i=0;i<history_count;i++) {
        cJSON *r=cJSON_CreateObject();cJSON_AddItemToArray(events,r);event_t *v=&history[i];
        cJSON_AddNumberToObject(r,"sequence",v->sequence);cJSON_AddNumberToObject(r,"boot_id",v->boot);
        cJSON_AddNumberToObject(r,"uptime_ms",v->uptime_us/1000);cJSON_AddStringToObject(r,"state",pc_state_name(v->state));
        cJSON_AddStringToObject(r,"reason",pc_reason_name(v->reason));cJSON_AddNumberToObject(r,"current_a",v->current_a);
        cJSON_AddNumberToObject(r,"temperature_c",v->temperature_c);
    }
    xSemaphoreGive(mutex);
}
cJSON *system_config_json(void) {
    xSemaphoreTake(mutex,portMAX_DELAY);pc_config_t cfg=config;xSemaphoreGive(mutex);
    cJSON *j=cJSON_CreateObject();if(!j) return NULL;
    cJSON_AddNumberToObject(j,"version",cfg.version);cJSON_AddBoolToObject(j,"commissioned",cfg.commissioned);
    cJSON_AddNumberToObject(j,"current_limit_a",cfg.current_limit_a);
    cJSON_AddNumberToObject(j,"temperature_limit_c",cfg.temperature_limit_c);
    cJSON_AddNumberToObject(j,"current_scale_a_per_v",cfg.current_scale_a_per_v);return j;
}
esp_err_t system_config_get(httpd_req_t *req) {
    if(!request_authorized(req)) return ESP_OK;
    cJSON *j=system_config_json();char *json=cJSON_PrintUnformatted(j);cJSON_Delete(j);
    if(!json) return ESP_ERR_NO_MEM;
    httpd_resp_set_type(req,"application/json");esp_err_t e=httpd_resp_sendstr(req,json);free(json);return e;
}
esp_err_t system_config_apply(const cJSON *j) {
    pc_config_t cfg={0};bool valid=cJSON_IsObject(j)&&cJSON_GetArraySize(j)==5;
    const char *names[]={"version","current_limit_a","temperature_limit_c","current_scale_a_per_v"};double values[4];
    for(int i=0;i<4;i++) {const cJSON *v=cJSON_GetObjectItemCaseSensitive(j,names[i]);values[i]=cJSON_GetNumberValue(v);valid=valid&&cJSON_IsNumber(v)&&isfinite(values[i]);}
    const cJSON *commissioned=cJSON_GetObjectItemCaseSensitive(j,"commissioned");valid=valid&&cJSON_IsBool(commissioned);
    if(valid && values[0]>=1 && values[0]<=UINT32_MAX && floor(values[0])==values[0]) {
        cfg=(pc_config_t){(uint32_t)values[0],cJSON_IsTrue(commissioned),(float)values[1],(float)values[2],(float)values[3]};
    } else valid=false;
    if(!valid||!pc_config_valid(&cfg)) return ESP_ERR_INVALID_ARG;
    /* Serialize USB and HTTP updates through the commit. Protection must never wait on NVS. */
    static portMUX_TYPE gate=portMUX_INITIALIZER_UNLOCKED;
    static bool updating;
    portENTER_CRITICAL(&gate);bool busy=updating;if(!busy) updating=true;portEXIT_CRITICAL(&gate);
    if(busy) return ESP_ERR_INVALID_STATE;
    xSemaphoreTake(mutex,portMAX_DELAY);
    if(cfg.version<=config.version) {
        xSemaphoreGive(mutex);portENTER_CRITICAL(&gate);updating=false;portEXIT_CRITICAL(&gate);
        return ESP_ERR_INVALID_STATE;
    }
    open_requested=true;gpio_set_level(4,0);config.commissioned=false;xSemaphoreGive(mutex);
    esp_err_t e=nvs_set_blob(storage,"config",&cfg,sizeof(cfg));if(e==ESP_OK) e=nvs_commit(storage);
    xSemaphoreTake(mutex,portMAX_DELAY);
    if(e==ESP_OK) {config=cfg;input.current_valid=false;controller.healthy_since_us=-1;}
    else storage_ok=false;
    xSemaphoreGive(mutex);
    portENTER_CRITICAL(&gate);updating=false;portEXIT_CRITICAL(&gate);return e;
}
esp_err_t system_config_set(httpd_req_t *req) {
    if(!request_authorized(req)) return ESP_OK;
    if(req->content_len<=0||req->content_len>512) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Config body must be 1-512 bytes");
    char body[513];int got=0;
    while(got<req->content_len) {int n=httpd_req_recv(req,body+got,req->content_len-got);if(n<=0) return ESP_FAIL;got+=n;}body[got]=0;
    cJSON *j=cJSON_ParseWithLengthOpts(body,(size_t)got+1,NULL,true);
    esp_err_t e=system_config_apply(j);cJSON_Delete(j);
    if(e==ESP_ERR_INVALID_ARG) return httpd_resp_send_err(req,HTTPD_400_BAD_REQUEST,"Invalid config; bench current limit must be <= 1 A");
    if(e==ESP_ERR_INVALID_STATE) {httpd_resp_set_status(req,"409 Conflict");return httpd_resp_sendstr(req,"Version must increase or another update is in progress");}
    if(e!=ESP_OK) return httpd_resp_send_err(req,HTTPD_500_INTERNAL_SERVER_ERROR,"Config storage failed; relay open");
    return httpd_resp_sendstr(req,"Saved. Local re-arm required.");
}
void system_request_open(void) {
    xSemaphoreTake(mutex,portMAX_DELAY);open_requested=true;gpio_set_level(4,0);xSemaphoreGive(mutex);
}
esp_err_t system_open(httpd_req_t *req) {
    if(!request_authorized(req)) return ESP_OK;
    system_request_open();return httpd_resp_sendstr(req,"Relay opening; remote re-arm is not supported.");
}
