#include "device_settings.h"
#include "serial_setup.h"
#include "project_config.h"
#include "calibration.h"
#include "fusion_core.h"
#include "thermal_sensor.h"
#include "system_control.h"
#include "telemetry.h"
#include <time.h>
#include <stdatomic.h>
#include "network.h"
#include "jpeg_decoder.h"
#include "esp_http_client.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_random.h"
#include "driver/gpio.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "cJSON.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#define RGB_BYTES (SMARTDB_FRAME_WIDTH*SMARTDB_FRAME_HEIGHT*3)
static SemaphoreHandle_t lock;
static fc_calibration_t calibration;
static uint8_t *published_bmp;
static size_t bmp_size;
static bool ready;
static atomic_bool network_ready;
static int64_t published_start;
static uint32_t generation;
static char reason[80]="starting",camera_frame[64];
static fc_measurement_t measurements[FC_MAX_REGIONS];
static float rise_per_min[FC_MAX_REGIONS];
static const size_t region_count=sizeof(installation_regions)/sizeof(installation_regions[0]);
static void unavailable(const char *why) {
    xSemaphoreTake(lock,portMAX_DELAY);ready=false;snprintf(reason,sizeof(reason),"%s",why);xSemaphoreGive(lock);
    ESP_LOGW("fusion","%s",why);
}
typedef struct {char id[80],boot[24],seq[24],policy[40];} camera_headers_t;
static esp_err_t camera_event(esp_http_client_event_t *e) {
    if(e->event_id!=HTTP_EVENT_ON_HEADER) return ESP_OK;
    camera_headers_t *h=e->user_data;char *dst=NULL;size_t size=0;
    if(!strcasecmp(e->header_key,"X-Camera-ID")) {dst=h->id;size=sizeof(h->id);}
    if(!strcasecmp(e->header_key,"X-Camera-Boot")) {dst=h->boot;size=sizeof(h->boot);}
    if(!strcasecmp(e->header_key,"X-Camera-Sequence")) {dst=h->seq;size=sizeof(h->seq);}
    if(!strcasecmp(e->header_key,"X-Capture-Policy")) {dst=h->policy;size=sizeof(h->policy);}
    if(dst) snprintf(dst,size,"%s",e->header_value);
    return ESP_OK;
}
static esp_err_t fetch_camera(uint8_t *jpeg,size_t *len,int64_t *start,int64_t *end,char *frame,size_t frame_size) {
    camera_headers_t headers={0};
    esp_http_client_config_t cfg={.url=device_settings()->camera_url,.timeout_ms=1500,.disable_auto_redirect=true,
        .event_handler=camera_event,.user_data=&headers,.buffer_size=2048};
    esp_http_client_handle_t client=esp_http_client_init(&cfg);if(!client) return ESP_ERR_NO_MEM;
    char auth[128];snprintf(auth,sizeof(auth),"Bearer %s",device_settings()->api_token);
    esp_http_client_set_header(client,"Authorization",auth);
    *start=esp_timer_get_time();esp_err_t err=esp_http_client_open(client,0);
    if(err==ESP_OK) {
        int64_t content=esp_http_client_fetch_headers(client);
        if(content<=0||content>SMARTDB_MAX_JPEG||esp_http_client_get_status_code(client)!=200
           ||strcmp(headers.id,device_settings()->camera_id)||strcmp(headers.policy,"fresh-after-request")||!headers.boot[0]||!headers.seq[0]) err=ESP_ERR_INVALID_RESPONSE;
        else {
            size_t got=0;
            while(got<(size_t)content) {
                if(esp_timer_get_time()-*start>1500000) {err=ESP_ERR_TIMEOUT;break;}
                int n=esp_http_client_read(client,(char*)jpeg+got,(int)(content-got));
                if(n<=0) {err=ESP_ERR_INVALID_RESPONSE;break;}got+=(size_t)n;
            }
            *len=got;
            if(err==ESP_OK) snprintf(frame,frame_size,"%s:%s",headers.boot,headers.seq);
        }
    }
    *end=esp_timer_get_time();esp_http_client_cleanup(client);return err;
}
static esp_err_t decode(uint8_t *jpeg,size_t len,uint8_t *rgb) {
    esp_jpeg_image_cfg_t cfg={.indata=jpeg,.indata_size=len,.outbuf=rgb,.outbuf_size=RGB_BYTES,
        .out_format=JPEG_IMAGE_FORMAT_RGB888,.out_scale=JPEG_IMAGE_SCALE_0};
    esp_jpeg_image_output_t info;
    esp_err_t err=esp_jpeg_get_image_info(&cfg,&info);if(err!=ESP_OK) return err;
    if(info.width!=SMARTDB_FRAME_WIDTH||info.height!=SMARTDB_FRAME_HEIGHT||info.output_len!=RGB_BYTES) return ESP_ERR_INVALID_SIZE;
    return esp_jpeg_decode(&cfg,&info);
}
static void *external(size_t size) {return heap_caps_malloc(size,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);}
static void fusion_task(void *unused) {
    (void)unused;
    uint8_t *jpeg=external(SMARTDB_MAX_JPEG),*rgb=external(RGB_BYTES),*fused=external(RGB_BYTES),*bmp=external(bmp_size);
    fc_thermal_t *thermal=external(sizeof(*thermal));
    if(!jpeg||!rgb||!fused||!bmp||!thermal) {
        free(jpeg);free(rgb);free(fused);free(bmp);free(thermal);unavailable("PSRAM allocation failed");vTaskDelete(NULL);return;
    }
    fc_measurement_t previous[FC_MAX_REGIONS]={0};int64_t previous_time=0;
    for(;;) {
        if(!SMARTDB_DEMO && !atomic_load(&network_ready)) {vTaskDelay(pdMS_TO_TICKS(500));continue;}
        size_t jpeg_len=0;int64_t rs,re;char frame[64];
        if(SMARTDB_DEMO) {
            rs=re=esp_timer_get_time();fc_demo(thermal,rgb,SMARTDB_FRAME_WIDTH,SMARTDB_FRAME_HEIGHT,rs);
            snprintf(frame,sizeof(frame),"synthetic");
        } else {
            if(fetch_camera(jpeg,&jpeg_len,&rs,&re,frame,sizeof(frame))!=ESP_OK || decode(jpeg,jpeg_len,rgb)!=ESP_OK) {
                unavailable("fresh camera JPEG unavailable");previous_time=0;goto next;
            }
            if(!system_thermal_snapshot(thermal)) {unavailable("thermal frame unavailable");previous_time=0;goto next;}
        }
        if(!fc_pair_valid(thermal,rs,re,esp_timer_get_time(),SMARTDB_PAIR_WINDOW_US,SMARTDB_MAX_AGE_US)) {
            unavailable("capture window too wide or frame stale");previous_time=0;goto next;
        }
        if(!fc_calibration_valid(&calibration)) {unavailable("camera alignment not configured");previous_time=0;goto next;}
        fc_measurement_t current[FC_MAX_REGIONS];
        if(!fc_measure(&calibration,thermal,installation_regions,region_count,current)
           ||!fc_render(&calibration,thermal,rgb,fused,RGB_BYTES)||!fc_bmp(fused,calibration.width,calibration.height,bmp,bmp_size)) {
            unavailable("fusion configuration invalid");previous_time=0;goto next;
        }
        bool supported=false;for(size_t i=0;i<region_count;i++) supported|=current[i].supported;
        if(!supported) {unavailable("no adequately resolved component region");previous_time=0;goto next;}
        int64_t captured=thermal->start_us<rs?thermal->start_us:rs;
        if(esp_timer_get_time()-captured>SMARTDB_MAX_AGE_US) {unavailable("frame expired during processing");previous_time=0;goto next;}
        xSemaphoreTake(lock,portMAX_DELAY);
        memcpy(published_bmp,bmp,bmp_size);memcpy(measurements,current,sizeof(current));
        for(size_t i=0;i<region_count;i++) {
            rise_per_min[i]=NAN;
            if(previous_time && current[i].supported && previous[i].supported && thermal->end_us>previous_time)
                rise_per_min[i]=(current[i].max_c-previous[i].max_c)*60000000.0f/(thermal->end_us-previous_time);
        }
        memcpy(previous,current,sizeof(current));previous_time=thermal->end_us;
        published_start=captured;generation++;ready=true;
        snprintf(reason,sizeof(reason),"%s",SMARTDB_DEMO?"synthetic demonstration":"registered fusion");
        snprintf(camera_frame,sizeof(camera_frame),"%s",frame);xSemaphoreGive(lock);
next:
        vTaskDelay(pdMS_TO_TICKS(250));
    }
}
static cJSON *snapshot_json(void) {
    cJSON *root=cJSON_CreateObject();if(!root) return NULL;
    xSemaphoreTake(lock,portMAX_DELAY);
    bool fresh=ready&&esp_timer_get_time()-published_start<=SMARTDB_MAX_AGE_US;
    cJSON_AddBoolToObject(root,"ready",fresh);cJSON_AddBoolToObject(root,"synthetic",SMARTDB_DEMO);
    cJSON_AddStringToObject(root,"reason",ready&&!fresh?"frame stale":reason);
    cJSON_AddStringToObject(root,"installation_id",device_settings()->installation_id);
    cJSON_AddStringToObject(root,"camera_id",device_settings()->camera_id);
    cJSON_AddStringToObject(root,"camera_frame_id",camera_frame);
    cJSON_AddStringToObject(root,"calibration_version",calibration.version);
    cJSON_AddNumberToObject(root,"sequence",generation);
    cJSON_AddNumberToObject(root,"display_min_c",calibration.display_min_c);
    cJSON_AddNumberToObject(root,"display_max_c",calibration.display_max_c);

    cJSON *regions=cJSON_AddArrayToObject(root,"regions");
    for(size_t i=0;i<region_count;i++) {
        cJSON *r=cJSON_CreateObject();cJSON_AddItemToArray(regions,r);
        cJSON_AddStringToObject(r,"id",installation_regions[i].id);
        cJSON_AddBoolToObject(r,"supported",fresh&&measurements[i].supported);
        cJSON_AddBoolToObject(r,"ambiguous",measurements[i].ambiguous);
        cJSON_AddNumberToObject(r,"samples",measurements[i].samples);
        cJSON_AddNumberToObject(r,"boundary_samples",measurements[i].boundary_samples);
        /* cJSON serializes non-finite numbers as null. Never expose stale temperatures. */
        cJSON_AddNumberToObject(r,"max_c",fresh?measurements[i].max_c:NAN);
        cJSON_AddNumberToObject(r,"mean_c",fresh?measurements[i].mean_c:NAN);
        cJSON_AddNumberToObject(r,"rise_c_per_min",fresh?rise_per_min[i]:NAN);
    }
    xSemaphoreGive(lock);
    return root;
}
static char *telemetry_payload(void) {
    static uint64_t boot_nonce;
    static uint32_t sample_sequence;
    if(!boot_nonce) esp_fill_random(&boot_nonce,sizeof(boot_nonce));
    cJSON *root=cJSON_CreateObject(),*vision=snapshot_json();
    if(!root||!vision) {cJSON_Delete(root);cJSON_Delete(vision);return NULL;}
    cJSON_AddItemToObject(root,"vision",vision);
    char sample_id[48];snprintf(sample_id,sizeof(sample_id),"%016llx:%lu",(unsigned long long)boot_nonce,(unsigned long)++sample_sequence);
    cJSON_AddStringToObject(root,"sample_id",sample_id);
    system_add_status(root);
    cJSON_AddNullToObject(root,"voltage");cJSON_AddNullToObject(root,"power");
    cJSON_AddBoolToObject(root,"synthetic",SMARTDB_DEMO);
    cJSON_AddNumberToObject(root,"uptime_ms",esp_timer_get_time()/1000);
    time_t now=time(NULL);struct tm utc;char iso[32];
    if(now>=1704067200 && gmtime_r(&now,&utc) && strftime(iso,sizeof(iso),"%Y-%m-%dT%H:%M:%SZ",&utc)) {
        cJSON_AddStringToObject(root,"timestamp",iso);cJSON_AddStringToObject(root,"time_quality","synced");
    } else {cJSON_AddNullToObject(root,"timestamp");cJSON_AddStringToObject(root,"time_quality","unknown");}
    char *json=cJSON_PrintUnformatted(root);cJSON_Delete(root);return json;
}
static telemetry_frame_t cloud_frame(void) {
    telemetry_frame_t frame={0};uint8_t *copy=external(bmp_size);if(!copy) return frame;
    xSemaphoreTake(lock,portMAX_DELAY);
    int64_t age=esp_timer_get_time()-published_start;
    if(ready && age>=0 && age<=SMARTDB_MAX_AGE_US) {
        memcpy(copy,published_bmp,bmp_size);frame=(telemetry_frame_t){.bytes=copy,.size=bmp_size,
            .sequence=generation,.age_ms=(uint32_t)(age/1000),.synthetic=SMARTDB_DEMO};
    }
    xSemaphoreGive(lock);if(!frame.bytes) free(copy);return frame;
}
static esp_err_t status(httpd_req_t *req) {
    if(!request_authorized(req)) return ESP_OK;
    cJSON *root=snapshot_json();if(!root) return ESP_ERR_NO_MEM;
    system_add_status(root);char *json=cJSON_PrintUnformatted(root);cJSON_Delete(root);
    if(!json) return ESP_ERR_NO_MEM;
    httpd_resp_set_type(req,"application/json");esp_err_t err=httpd_resp_sendstr(req,json);free(json);return err;
}
static esp_err_t picture(httpd_req_t *req) {
    if(!request_authorized(req)) return ESP_OK;
    uint8_t *snapshot=external(bmp_size);if(!snapshot) return ESP_ERR_NO_MEM;
    xSemaphoreTake(lock,portMAX_DELAY);
    bool fresh=ready&&esp_timer_get_time()-published_start<=SMARTDB_MAX_AGE_US;
    uint32_t seq=generation;if(fresh) memcpy(snapshot,published_bmp,bmp_size);xSemaphoreGive(lock);
    esp_err_t err;
    if(!fresh) {httpd_resp_set_status(req,"503 Service Unavailable");err=httpd_resp_sendstr(req,"Fused frame unavailable; see /status");}
    else {char text[16];snprintf(text,sizeof(text),"%lu",(unsigned long)seq);httpd_resp_set_hdr(req,"X-Fusion-Sequence",text);
        httpd_resp_set_type(req,"image/bmp");err=httpd_resp_send(req,(const char*)snapshot,bmp_size);}
    free(snapshot);return err;
}
static esp_err_t page(httpd_req_t *req) {
    httpd_resp_set_type(req,"text/html");
    return httpd_resp_sendstr(req,
        "<!doctype html><meta name='viewport' content='width=device-width'><title>SmartDB fusion</title>"
        "<h1>SmartDB RGB + thermal</h1><p>Interpolated thermal overlay. Temperatures use native sensor samples.</p>"
        "<label>API token <input id='token' type='password' autocomplete='off'></label> <button id='start'>Connect</button>"
        "<p id='state'>Disconnected</p><img id='view' width='640' style='max-width:100%;image-rendering:auto'><pre id='details'></pre>"
        "<script>let active=false,url;document.getElementById('start').onclick=()=>{if(!active){active=true;tick()}};"
        "async function tick(){const state=document.getElementById('state'),view=document.getElementById('view');"
        "try{const headers={Authorization:'Bearer '+document.getElementById('token').value};"
        "let r=await fetch('/status',{headers,cache:'no-store'});if(!r.ok)throw Error('Status '+r.status);"
        "let s=await r.json();state.textContent=(s.synthetic?'SYNTHETIC DEMO — ':'')+s.reason+' | '+s.display_min_c+' to '+s.display_max_c+' C (blue/red/yellow)';"
        "document.getElementById('details').textContent=JSON.stringify(s,null,2);if(!s.ready)throw Error(s.reason);"
        "r=await fetch('/fused.bmp',{headers,cache:'no-store'});if(!r.ok)throw Error('Image '+r.status);"
        "let next=URL.createObjectURL(await r.blob());view.src=next;if(url)URL.revokeObjectURL(url);url=next;"
        "}catch(e){state.textContent=e.message;view.removeAttribute('src')}setTimeout(tick,1000)}</script>");
}
static void network_task(void *arg) {
    (void)arg;
    if(network_start()!=ESP_OK) {ESP_LOGE("network","Network configuration unavailable; local sensing/protection continues");vTaskDelete(NULL);return;}
    httpd_handle_t h=web_server_start();
    const httpd_uri_t routes[]={
        {.uri="/",.method=HTTP_GET,.handler=page},
        {.uri="/status",.method=HTTP_GET,.handler=status},
        {.uri="/fused.bmp",.method=HTTP_GET,.handler=picture},
        {.uri="/config",.method=HTTP_GET,.handler=system_config_get},
        {.uri="/config",.method=HTTP_PUT,.handler=system_config_set},
        {.uri="/relay/open",.method=HTTP_POST,.handler=system_open}};
    for(unsigned i=0;i<sizeof(routes)/sizeof(routes[0]);i++) ESP_ERROR_CHECK(httpd_register_uri_handler(h,&routes[i]));
    atomic_store(&network_ready,true);telemetry_start(telemetry_payload,cloud_frame);vTaskDelete(NULL);
}
void app_main(void) {
    ESP_ERROR_CHECK(system_start());
    ESP_ERROR_CHECK(device_settings_init());
    ESP_ERROR_CHECK(serial_setup_start());
    calibration=installation_calibration;
    if(SMARTDB_DEMO) {
        calibration.enabled=true;calibration.version="synthetic-demo-only";
        const float h[9]={31.0f/319,0,0,0,23.0f/239,0,0,0,1};memcpy(calibration.rgb_to_thermal,h,sizeof(h));
    }
    if(calibration.width!=SMARTDB_FRAME_WIDTH||calibration.height!=SMARTDB_FRAME_HEIGHT||region_count>FC_MAX_REGIONS) {
        ESP_LOGE("fusion","Only QVGA RGB and up to eight regions supported");return;
    }
    bmp_size=fc_bmp_size(calibration.width,calibration.height);lock=xSemaphoreCreateMutex();published_bmp=external(bmp_size);
    if(!lock||!published_bmp) {ESP_LOGE("fusion","PSRAM/mutex allocation failed");return;}
    if(xTaskCreatePinnedToCore(network_task,"network_start",8192,NULL,3,NULL,0)!=pdPASS) unavailable("network task allocation failed");
    if(xTaskCreatePinnedToCore(fusion_task,"fusion",16384,NULL,4,NULL,0)!=pdPASS) unavailable("fusion task allocation failed");
}
