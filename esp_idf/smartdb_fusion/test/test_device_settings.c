#include "device_settings.h"
#include "nvs.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
static device_settings_t stored,pending;
static bool exists,fail_commit;
esp_err_t nvs_flash_init(void) {return ESP_OK;}
esp_err_t nvs_open(const char *name,int mode,nvs_handle_t *h) {(void)mode;assert(!strcmp(name,"connection"));*h=1;return ESP_OK;}
void nvs_close(nvs_handle_t h) {(void)h;}
esp_err_t nvs_get_blob(nvs_handle_t h,const char *key,void *data,size_t *size) {
    (void)h;assert(!strcmp(key,"settings_v1"));if(!exists) return ESP_ERR_NVS_NOT_FOUND;
    assert(*size>=sizeof(stored));memcpy(data,&stored,sizeof(stored));*size=sizeof(stored);return ESP_OK;
}
esp_err_t nvs_set_blob(nvs_handle_t h,const char *key,const void *data,size_t size) {
    (void)h;assert(!strcmp(key,"settings_v1"));assert(size==sizeof(pending));memcpy(&pending,data,size);return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t h) {(void)h;if(fail_commit) return ESP_FAIL;stored=pending;exists=true;return ESP_OK;}
int main(void) {
    assert(device_settings_init()==ESP_OK);
    cJSON *j=cJSON_Parse("{\"wifi_ssid\":\"test-network\",\"wifi_password\":\"test-password\",\"api_token\":\"test-token-at-least-24-characters\",\"camera_url\":\"http://192.168.1.50/capture\",\"camera_id\":\"camera-1\",\"installation_id\":\"panel-1\",\"telemetry_url\":\"\",\"telemetry_token\":\"\"}");
    assert(device_settings_save(j)==ESP_OK);
    /* Save does not race readers of the active boot snapshot. Restart activates it. */
    assert(strcmp(device_settings()->wifi_ssid,"test-network"));
    assert(device_settings_init()==ESP_OK);assert(!strcmp(device_settings()->wifi_ssid,"test-network"));
    cJSON *public=device_settings_public();char *text=cJSON_PrintUnformatted(public);
    assert(!strstr(text,"test-password"));assert(!strstr(text,"test-token-at-least"));
    assert(!cJSON_GetObjectItem(public,"api_token"));assert(cJSON_IsTrue(cJSON_GetObjectItem(public,"api_token_set")));
    free(text);cJSON_Delete(public);
    cJSON_ReplaceItemInObject(j,"wifi_password",cJSON_CreateString("short"));assert(device_settings_save(j)==ESP_ERR_INVALID_ARG);
    cJSON_ReplaceItemInObject(j,"wifi_password",cJSON_CreateString("another-test-password"));
    cJSON_ReplaceItemInObject(j,"telemetry_url",cJSON_CreateString("http://server/telemetry"));assert(device_settings_save(j)==ESP_ERR_INVALID_ARG);
    cJSON_ReplaceItemInObject(j,"telemetry_url",cJSON_CreateString("https://server/telemetry"));assert(device_settings_save(j)==ESP_ERR_INVALID_ARG);
    cJSON_ReplaceItemInObject(j,"telemetry_token",cJSON_CreateString("test-cloud-token"));assert(device_settings_save(j)==ESP_OK);
    cJSON_ReplaceItemInObject(j,"wifi_ssid",cJSON_CreateString("other-network"));fail_commit=true;
    assert(device_settings_save(j)==ESP_FAIL);assert(device_settings_init()==ESP_OK);
    assert(!strcmp(device_settings()->wifi_ssid,"test-network"));
    fail_commit=false;assert(device_settings_save(j)==ESP_OK);assert(device_settings_init()==ESP_OK);
    assert(!strcmp(device_settings()->wifi_ssid,"other-network"));
    memset(stored.api_token,'x',sizeof(stored.api_token));
    assert(device_settings_init()==ESP_OK);assert(!device_settings()->wifi_ssid[0]); /* USB recovery remains possible. */
    assert(device_settings_save(j)==ESP_OK);assert(device_settings_init()==ESP_OK);
    cJSON_DeleteItemFromObject(j,"camera_id");assert(device_settings_save(j)==ESP_ERR_INVALID_ARG);
    cJSON_Delete(j);puts("Device settings tests passed: persistence, restart, redaction, validation, storage failure and recovery.");
}
