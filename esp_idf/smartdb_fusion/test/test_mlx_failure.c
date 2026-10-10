#include <stdint.h>
#include "MLX90640_API.h"
#include "MLX90640_I2C_Driver.h"
#include <assert.h>
#include <stdio.h>
void MLX90640_I2CInit(void) {}
void MLX90640_I2CFreqSet(int f) {(void)f;}
int MLX90640_I2CGeneralReset(void) {return 0;}
int MLX90640_I2CWrite(uint8_t a,uint16_t r,uint16_t v) {(void)a;(void)r;(void)v;return 0;}
int MLX90640_I2CRead(uint8_t a,uint16_t r,uint16_t n,uint16_t *data) {
    (void)a;for(unsigned i=0;i<n;i++) data[i]=1000;
    if(r==0x8000) data[0]=8;
    if(r==0x0700) data[0]=0x7fff; /* Invalid auxiliary measurement must fail this frame. */
    return 0;
}
int main(void) {
    uint16_t frame[834]={0};assert(MLX90640_GetFrameData(0x33,frame)==-MLX90640_FRAME_DATA_ERROR);
    puts("MLX invalid auxiliary-data regression passed.");
}
