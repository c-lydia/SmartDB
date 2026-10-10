#include "serial_setup.h"
#include "device_settings.h"
#include "network.h"
#include "driver/uart.h"
#include "esp_system.h"
#include "esp_netif.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#if CONFIG_IDF_TARGET_ESP32S3
#include "system_control.h"
#define BOARD "smartdb_s3"
#else
#define BOARD "esp32cam"
#endif
#define LINE_SIZE 4096
#define PREFIX "SMARTDB "
static void reply(cJSON *j) {
    char *s=cJSON_PrintUnformatted(j);
    if(s) {printf("\n" PREFIX "%s\n",s);fflush(stdout);free(s);}
    cJSON_Delete(j);
}
static void process(const char *line) {
    cJSON *request=cJSON_ParseWithOpts(line,NULL,true);
    const cJSON *id=cJSON_GetObjectItemCaseSensitive(request,"id");
    const char *op=cJSON_GetStringValue(cJSON_GetObjectItemCaseSensitive(request,"op"));
    cJSON *response=cJSON_CreateObject();if(!response) {cJSON_Delete(request);return;}
    if(cJSON_IsString(id)) cJSON_AddStringToObject(response,"id",id->valuestring);
    esp_err_t e=ESP_ERR_INVALID_ARG;bool restart=false;
    if(op&&cJSON_IsString(id)&&strlen(id->valuestring)<=32) {
        const cJSON *data=cJSON_GetObjectItemCaseSensitive(request,"data");
        if(!strcmp(op,"info")) {
            e=ESP_OK;cJSON_AddNumberToObject(response,"protocol",1);cJSON_AddStringToObject(response,"board",BOARD);
            cJSON_AddNumberToObject(response,"uptime_ms",esp_timer_get_time()/1000);
            uint8_t mac[6];char identity[18];esp_read_mac(mac,ESP_MAC_WIFI_STA);
            snprintf(identity,sizeof(identity),"%02x:%02x:%02x:%02x:%02x:%02x",mac[0],mac[1],mac[2],mac[3],mac[4],mac[5]);
            cJSON_AddStringToObject(response,"device_id",identity);
            cJSON_AddItemToObject(response,"settings",device_settings_public());
            esp_ip4_addr_t ip={.addr=network_ipv4()};
            char address[16]="";if(ip.addr) snprintf(address,sizeof(address),IPSTR,IP2STR(&ip));
            cJSON_AddStringToObject(response,"ip",address);
#if CONFIG_IDF_TARGET_ESP32S3
            system_add_status(response);
#endif
        } else if(!strcmp(op,"save_settings")) {
#if CONFIG_IDF_TARGET_ESP32S3
            system_request_open();
#endif
            e=device_settings_save(data);
            if(e==ESP_OK) cJSON_AddBoolToObject(response,"restart_required",true);
        } else if(!strcmp(op,"restart")) {
#if CONFIG_IDF_TARGET_ESP32S3
            system_request_open();
#endif
            e=ESP_OK;restart=true;
#if CONFIG_IDF_TARGET_ESP32S3
        } else if(!strcmp(op,"read_control")) {
            e=ESP_OK;cJSON_AddItemToObject(response,"config",system_config_json());
        } else if(!strcmp(op,"write_control")) {
            e=system_config_apply(data);
        } else if(!strcmp(op,"open_relay")) {
            system_request_open();e=ESP_OK;
#endif
        }
    }
    cJSON_AddBoolToObject(response,"ok",e==ESP_OK);
    if(e!=ESP_OK) cJSON_AddStringToObject(response,"error",esp_err_to_name(e));
    cJSON_Delete(request);reply(response);
    if(restart) {vTaskDelay(pdMS_TO_TICKS(200));esp_restart();}
}
static void task(void *unused) {
    (void)unused;char *line=malloc(LINE_SIZE);if(!line) {vTaskDelete(NULL);return;}
    size_t length=0;bool overflow=false;
    for(;;) {
        char c;
        if(uart_read_bytes(CONFIG_ESP_CONSOLE_UART_NUM,&c,1,pdMS_TO_TICKS(100))!=1) continue;
        if(c=='\n') {
            line[length]=0;
            if(!overflow&&!strncmp(line,PREFIX,strlen(PREFIX))) process(line+strlen(PREFIX));
            memset(line,0,length);length=0;overflow=false;
        } else if(c!='\r') {
            if(length<LINE_SIZE-1) line[length++]=c;else overflow=true;
        }
    }
}
esp_err_t serial_setup_start(void) {
    esp_err_t e=uart_driver_install(CONFIG_ESP_CONSOLE_UART_NUM,8192,0,0,NULL,0);
    if(e!=ESP_OK) return e;
    return xTaskCreate(task,"usb_setup",12288,NULL,2,NULL)==pdPASS?ESP_OK:ESP_ERR_NO_MEM;
}
