#include "device_settings.h"
#include "telemetry.h"
#include "cloud_control.h"
#include "project_config.h"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"
#include "esp_netif_sntp.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
static telemetry_snapshot_fn snapshot;
static telemetry_frame_fn frame_snapshot;
static QueueHandle_t pending;
static TaskHandle_t collector;
typedef struct {char body[2048];size_t length;bool overflow;} response_t;
static esp_err_t response_event(esp_http_client_event_t *event) {
    response_t *r=event->user_data;
    if(r&&event->event_id==HTTP_EVENT_ON_DATA && event->data_len>0) {
        if((size_t)event->data_len>=sizeof(r->body)-r->length) r->overflow=true;
        else if(!r->overflow) {memcpy(r->body+r->length,event->data,event->data_len);r->length+=event->data_len;r->body[r->length]=0;}
    }
    return ESP_OK;
}
static void handle_command(const response_t *response) {
    if(response->overflow||!response->length) return;
    cJSON *root=cJSON_ParseWithOpts(response->body,NULL,true);
    const cJSON *command=cJSON_GetObjectItemCaseSensitive(root,"command");
    if(!cJSON_IsObject(command)) {cJSON_Delete(root);return;}
    const char *url=device_settings()->telemetry_url;size_t length=strlen(url);
    const char suffix[]="/telemetry";
    if(length<sizeof(suffix)-1||strcmp(url+length-(sizeof(suffix)-1),suffix)) {cJSON_Delete(root);return;}
    uint64_t id=0;bool fresh=false;esp_err_t result=cloud_control_apply(command,&id,&fresh);
    cJSON_Delete(root);if(!id) return;
    if(fresh&&collector) xTaskNotifyGive(collector);
    char endpoint[320],body[192],token[768];
    snprintf(endpoint,sizeof(endpoint),"%.*s/commands/%llu/ack",(int)(length-(sizeof(suffix)-1)),url,(unsigned long long)id);
    snprintf(body,sizeof(body),"{\"status\":\"%s\",\"detail\":\"%s\"}",result==ESP_OK?"success":"failed",esp_err_to_name(result));
    snprintf(token,sizeof(token),"Bearer %s",device_settings()->telemetry_token);
    esp_http_client_config_t cfg={.url=endpoint,.method=HTTP_METHOD_POST,.timeout_ms=3000,
        .crt_bundle_attach=esp_crt_bundle_attach,.disable_auto_redirect=true};
    esp_http_client_handle_t client=esp_http_client_init(&cfg);if(!client) return;
    esp_http_client_set_header(client,"Authorization",token);esp_http_client_set_header(client,"Content-Type","application/json");
    esp_http_client_set_post_field(client,body,strlen(body));
    esp_err_t e=esp_http_client_perform(client);int status=esp_http_client_get_status_code(client);esp_http_client_cleanup(client);
    if(e!=ESP_OK||status!=204) ESP_LOGW("telemetry","Command acknowledgement not accepted; server may redeliver");
}
static void collect(void *arg) {
    (void)arg;
    for(;;) {
        char *json=snapshot();
        if(json && xQueueSend(pending,&json,0)!=pdTRUE) {
            char *old=NULL;if(xQueueReceive(pending,&old,0)==pdTRUE) free(old);
            if(xQueueSend(pending,&json,0)!=pdTRUE) free(json);
        }
        ulTaskNotifyTake(pdTRUE,pdMS_TO_TICKS(cloud_control_interval()*1000));
    }
}
static void upload_frame(void) {
    static int64_t last_attempt;
    int64_t now=esp_timer_get_time();
    if(!frame_snapshot || now-last_attempt<30000000) return;
    last_attempt=now;
    const char *url=device_settings()->telemetry_url;size_t length=strlen(url);
    const char suffix[]="/telemetry";
    if(length<sizeof(suffix)-1 || strcmp(url+length-(sizeof(suffix)-1),suffix)) return;
    telemetry_frame_t frame=frame_snapshot();if(!frame.bytes) return;
    char endpoint[320],token[768],sequence[24],age[24];
    snprintf(endpoint,sizeof(endpoint),"%.*s/fusion/frame",(int)(length-(sizeof(suffix)-1)),url);
    snprintf(token,sizeof(token),"Bearer %s",device_settings()->telemetry_token);
    snprintf(sequence,sizeof(sequence),"%lu",(unsigned long)frame.sequence);
    snprintf(age,sizeof(age),"%lu",(unsigned long)frame.age_ms);
    esp_http_client_config_t cfg={.url=endpoint,.method=HTTP_METHOD_POST,.timeout_ms=3000,
        .crt_bundle_attach=esp_crt_bundle_attach,.disable_auto_redirect=true};
    esp_http_client_handle_t client=esp_http_client_init(&cfg);
    if(client) {
        esp_http_client_set_header(client,"Authorization",token);esp_http_client_set_header(client,"Content-Type","image/bmp");
        esp_http_client_set_header(client,"X-Fusion-Sequence",sequence);esp_http_client_set_header(client,"X-Capture-Age-Ms",age);
        esp_http_client_set_header(client,"X-Synthetic",frame.synthetic?"true":"false");
        esp_http_client_set_post_field(client,(const char*)frame.bytes,frame.size);
        esp_err_t e=esp_http_client_perform(client);int status=esp_http_client_get_status_code(client);
        esp_http_client_cleanup(client);
        if(e!=ESP_OK||status!=202) ESP_LOGW("telemetry","Preview upload unavailable (HTTP %d)",status);
    }
    free(frame.bytes); /* Preview is best-effort; never retain stale images for retry. */
}
static void upload(void *arg) {
    (void)arg;char *json=NULL;unsigned backoff=5;
    for(;;) {
        if(!json) xQueueReceive(pending,&json,portMAX_DELAY);
        response_t response={0};
        esp_http_client_config_t cfg={.url=device_settings()->telemetry_url,.method=HTTP_METHOD_POST,.timeout_ms=3000,
            .crt_bundle_attach=esp_crt_bundle_attach,.disable_auto_redirect=true,.buffer_size=1024,
            .event_handler=response_event,.user_data=&response};
        esp_http_client_handle_t c=esp_http_client_init(&cfg);
        int status=0;esp_err_t e=ESP_FAIL;
        if(c) {
            char token[768];snprintf(token,sizeof(token),"Bearer %s",device_settings()->telemetry_token);
            esp_http_client_set_header(c,"Authorization",token);esp_http_client_set_header(c,"Content-Type","application/json");
            esp_http_client_set_post_field(c,json,strlen(json));e=esp_http_client_perform(c);
            status=esp_http_client_get_status_code(c);esp_http_client_cleanup(c);
        }
        if(e==ESP_OK && status==202) {free(json);json=NULL;backoff=5;handle_command(&response);upload_frame();}
        else {
            ESP_LOGW("telemetry","Upload not accepted (HTTP %d); retry in %u seconds",status,backoff);
            vTaskDelay(pdMS_TO_TICKS(backoff*1000));if(backoff<60) backoff=backoff*2>60?60:backoff*2;
        }
    }
}
void telemetry_start(telemetry_snapshot_fn fn,telemetry_frame_fn frame) {
    snapshot=fn;frame_snapshot=frame;
    if(cloud_control_init()!=ESP_OK) ESP_LOGW("telemetry","Cloud command storage unavailable; uploads remain available");
    esp_sntp_config_t ntp=ESP_NETIF_SNTP_DEFAULT_CONFIG(SMARTDB_SNTP_SERVER);
    if(esp_netif_sntp_init(&ntp)!=ESP_OK) ESP_LOGW("telemetry","SNTP unavailable; timestamp stays unknown");
    if(!device_settings()->telemetry_url[0]) {ESP_LOGI("telemetry","Uploads disabled; configure the Postman HTTPS telemetry URL");return;}
    size_t token_len=strlen(device_settings()->telemetry_token);
    if(strncmp(device_settings()->telemetry_url,"https://",8)||token_len<1||token_len>700) {
        ESP_LOGE("telemetry","HTTPS endpoint and bearer token required");return;
    }
    for(size_t i=0;i<token_len;i++) if(device_settings()->telemetry_token[i]<33||device_settings()->telemetry_token[i]>126) {ESP_LOGE("telemetry","Invalid token characters");return;}
    pending=xQueueCreate(12,sizeof(char*));if(!pending) return;
    if(xTaskCreate(collect,"telemetry_collect",8192,NULL,2,&collector)!=pdPASS) return;
    if(xTaskCreate(upload,"telemetry_upload",12288,NULL,2,NULL)!=pdPASS) ESP_LOGE("telemetry","Uploader allocation failed");
}
