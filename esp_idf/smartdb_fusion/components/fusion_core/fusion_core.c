#include "fusion_core.h"
#include <math.h>
#include <string.h>

static float clampf(float x, float lo, float hi) { return fminf(hi, fmaxf(lo, x)); }
static bool invert(const float *m, float *r) {
    float d=m[0]*(m[4]*m[8]-m[5]*m[7])-m[1]*(m[3]*m[8]-m[5]*m[6])+m[2]*(m[3]*m[7]-m[4]*m[6]);
    if (!isfinite(d) || fabsf(d)<1e-10f) return false;
    const float a[9]={m[4]*m[8]-m[5]*m[7], m[2]*m[7]-m[1]*m[8], m[1]*m[5]-m[2]*m[4],
        m[5]*m[6]-m[3]*m[8], m[0]*m[8]-m[2]*m[6], m[2]*m[3]-m[0]*m[5],
        m[3]*m[7]-m[4]*m[6], m[1]*m[6]-m[0]*m[7], m[0]*m[4]-m[1]*m[3]};
    for(int i=0;i<9;i++) { r[i]=a[i]/d; if(!isfinite(r[i])) return false; }
    return true;
}
static bool project(const float *m,float x,float y,float *u,float *v) {
    float d=m[6]*x+m[7]*y+m[8];
    if (!isfinite(d)||fabsf(d)<1e-7f) return false;
    *u=(m[0]*x+m[1]*y+m[2])/d; *v=(m[3]*x+m[4]*y+m[5])/d;
    return isfinite(*u)&&isfinite(*v);
}
bool fc_calibration_valid(const fc_calibration_t *c) {
    if(!c||!c->enabled||!c->version||!c->version[0]||!c->width||!c->height||c->width>640||c->height>480
       ||!isfinite(c->opacity)||c->opacity<0||c->opacity>1||!isfinite(c->display_min_c)
       ||!isfinite(c->display_max_c)||c->display_max_c<=c->display_min_c) return false;
    for(int i=0;i<9;i++) if(!isfinite(c->rgb_to_thermal[i])) return false;
    float inv[9]; if(!invert(c->rgb_to_thermal,inv)) return false;
    /* A projective horizon through the image is not a usable panel mapping. */
    float sign=0;
    for(int i=0;i<4;i++) {
        float x=(i&1)?c->width-1:0, y=(i&2)?c->height-1:0;
        float d=c->rgb_to_thermal[6]*x+c->rgb_to_thermal[7]*y+c->rgb_to_thermal[8];
        if(fabsf(d)<1e-7f || (sign!=0 && sign*d<=0)) return false;
        sign=d;
    }
    return true;
}
bool fc_pair_valid(const fc_thermal_t *t,int64_t rs,int64_t re,int64_t now,int64_t span,int64_t age) {
    if(!t||span<0||age<0||rs<0||re<rs||t->start_us<0||t->end_us<t->start_us||re>now||t->end_us>now) return false;
    int64_t first=rs<t->start_us?rs:t->start_us, last=re>t->end_us?re:t->end_us;
    return last-first<=span && now-first<=age;
}
static float cubic(float x) {
    x=fabsf(x);
    if(x<=1) return 1.5f*x*x*x-2.5f*x*x+1;
    if(x<2) return -.5f*x*x*x+2.5f*x*x-4*x+2;
    return 0;
}
bool fc_bicubic(const fc_thermal_t *t,float x,float y,float *out) {
    if(!t||!out||!isfinite(x)||!isfinite(y)||x<0||y<0||x>31||y>23) return false;
    int bx=(int)floorf(x),by=(int)floorf(y);
    float total=0,weight=0,lo=INFINITY,hi=-INFINITY;
    for(int dy=-1;dy<=2;dy++) for(int dx=-1;dx<=2;dx++) {
        float w=cubic(x-(bx+dx))*cubic(y-(by+dy));
        if(fabsf(w)<1e-8f) continue;
        int xx=(int)clampf(bx+dx,0,31),yy=(int)clampf(by+dy,0,23),i=yy*32+xx;
        if(!t->valid[i]||t->corrected[i]||!isfinite(t->celsius[i])) return false;
        lo=fminf(lo,t->celsius[i]);hi=fmaxf(hi,t->celsius[i]);
        total+=w*t->celsius[i];weight+=w;
    }
    if(fabsf(weight)<1e-8f) return false;
    *out=clampf(total/weight,lo,hi); /* Clip display ringing, never alter measurements. */
    return isfinite(*out);
}
bool fc_render(const fc_calibration_t *c,const fc_thermal_t *t,const uint8_t *rgb,uint8_t *dst,size_t size) {
    if(!fc_calibration_valid(c)||!t||!rgb||!dst||size<(size_t)c->width*c->height*3) return false;
    for(unsigned y=0;y<c->height;y++) for(unsigned x=0;x<c->width;x++) {
        size_t i=((size_t)y*c->width+x)*3;float u,v,temp;
        memcpy(dst+i,rgb+i,3);
        if(!project(c->rgb_to_thermal,x,y,&u,&v)||!fc_bicubic(t,u,v,&temp)) continue;
        float n=clampf((temp-c->display_min_c)/(c->display_max_c-c->display_min_c),0,1);
        /* Fixed blue -> red -> yellow scale; same limits on every frame. */
        float colour[3]={255*clampf(2*n,0,1),255*clampf(2*n-1,0,1),255*(1-clampf(2*n,0,1))};
        for(int k=0;k<3;k++) dst[i+k]=(uint8_t)lroundf((1-c->opacity)*rgb[i+k]+c->opacity*colour[k]);
    }
    return true;
}
static bool contains(const fc_region_t *r,float x,float y) {
    return x>=r->x0&&x<=r->x1&&y>=r->y0&&y<=r->y1;
}
bool fc_measure(const fc_calibration_t *c,const fc_thermal_t *t,const fc_region_t *r,size_t n,fc_measurement_t *out) {
    if(!fc_calibration_valid(c)||!t||!r||!out||!n||n>FC_MAX_REGIONS) return false;
    float inv[9];if(!invert(c->rgb_to_thermal,inv)) return false;
    for(size_t j=0;j<n;j++) {
        if(!r[j].id||!r[j].min_samples||!isfinite(r[j].x0)||!isfinite(r[j].x1)||!isfinite(r[j].y0)||!isfinite(r[j].y1)
           ||r[j].x0<0||r[j].y0<0||r[j].x1>=c->width||r[j].y1>=c->height||r[j].x1<=r[j].x0||r[j].y1<=r[j].y0) return false;
        out[j]=(fc_measurement_t){.max_c=NAN,.mean_c=NAN};
    }
    for(int y=0;y<24;y++) for(int x=0;x<32;x++) {
        int i=y*32+x;float u,v;
        if(!t->valid[i]||t->corrected[i]||!isfinite(t->celsius[i])||!project(inv,x,y,&u,&v)) continue;
        unsigned matches=0;bool hit[FC_MAX_REGIONS]={0};
        for(size_t j=0;j<n;j++) if(contains(&r[j],u,v)) {hit[j]=true;matches++;}
        for(size_t j=0;j<n;j++) if(hit[j]) {
            if(matches>1) {out[j].ambiguous=true;continue;}
            bool whole=true;
            for(int k=0;k<4;k++) {
                float a,b;
                if(!project(inv,x+((k&1)?.5f:-.5f),y+((k&2)?.5f:-.5f),&a,&b)||!contains(&r[j],a,b)) whole=false;
            }
            if(!whole) {out[j].boundary_samples++;continue;}
            if(out[j].samples==0) {out[j].max_c=t->celsius[i];out[j].mean_c=0;}
            out[j].max_c=fmaxf(out[j].max_c,t->celsius[i]);out[j].mean_c+=t->celsius[i];out[j].samples++;
        }
    }
    for(size_t j=0;j<n;j++) {
        if(out[j].samples) out[j].mean_c/=out[j].samples;
        out[j].supported=out[j].samples>=r[j].min_samples&&!out[j].ambiguous;
        if(!out[j].supported) {out[j].max_c=NAN;out[j].mean_c=NAN;}
    }
    return true;
}
void fc_demo(fc_thermal_t *t,uint8_t *rgb,unsigned w,unsigned h,int64_t now) {
    memset(t,0,sizeof(*t));t->start_us=now;t->end_us=now;
    for(int y=0;y<24;y++) for(int x=0;x<32;x++) {
        int i=y*32+x;float d=(x-20)*(x-20)+(y-12)*(y-12);
        t->celsius[i]=25+45*expf(-d/10);t->valid[i]=1;
    }
    for(unsigned y=0;y<h;y++) for(unsigned x=0;x<w;x++) {
        size_t i=((size_t)y*w+x)*3;
        bool edge=(x%(w/4)<3)||(y<h/8)||(y>h*7/8);
        rgb[i]=edge?190:65;rgb[i+1]=edge?190:75;rgb[i+2]=edge?190:85;
    }
}
size_t fc_bmp_size(unsigned w,unsigned h) {
    if(!w||!h||w>640||h>480) return 0;
    return 54+(((size_t)w*3+3)&~(size_t)3)*h;
}
static void le32(uint8_t *p,uint32_t x) { for(int i=0;i<4;i++) p[i]=(uint8_t)(x>>(8*i)); }
bool fc_bmp(const uint8_t *rgb,unsigned w,unsigned h,uint8_t *out,size_t size) {
    size_t len=fc_bmp_size(w,h);if(!rgb||!out||!len||size<len) return false;
    memset(out,0,len);out[0]='B';out[1]='M';le32(out+2,(uint32_t)len);le32(out+10,54);
    le32(out+14,40);le32(out+18,w);le32(out+22,(uint32_t)-(int32_t)h);out[26]=1;out[28]=24;
    size_t stride=((size_t)w*3+3)&~(size_t)3;le32(out+34,(uint32_t)(stride*h));
    for(unsigned y=0;y<h;y++) for(unsigned x=0;x<w;x++) {
        size_t s=((size_t)y*w+x)*3,d=54+y*stride+x*3;
        out[d]=rgb[s+2];out[d+1]=rgb[s+1];out[d+2]=rgb[s];
    }
    return true;
}
