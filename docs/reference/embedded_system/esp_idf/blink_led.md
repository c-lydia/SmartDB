# Blink LED: ESP-IDF Edition

## Purpose

This document describes the complete setup process for developing an ESP32 firmware project using ESP-IDF.

The goal of this project is to establish a working ESP-IDF development environment before moving to SmartDB firmware development.

This includes:

- ESP-IDF installation verification
- Toolchain configuration
- Project creation
- Component dependency setup
- Build system configuration
- Firmware flashing
- Debugging workflow

## Development Environment

### Host Machine

| Component | Version |
|-|-|
| OS | Ubuntu 24.04 |
| Framework | ESP-IDF v6.x |
| Build System | CMake + Ninja |
| Language | C/C++ |
| Python Environment | ESP-IDF managed Python |

ESP-IDF location:

``` bash
~/esp/esp-idf
```

Project location:

``` bash
~/projects/SmartDB/esp_idf/blink
```

## ESP-IDF Environment Setup

## Load ESP-IDF

Before using ESP-IDF commands:

``` bash
source ~/esp/esp-idf/export.sh
```

This configures:

* ESP-IDF tools
* Compiler
* Python environment
* CMake integration
* Ninja build system

Verify:

``` bash
idf.py --version
```

Expected:

``` bash
ESP-IDF v6.x
```

## Creating ESP-IDF Project

Create project:

``` bash
idf.py create-project blink
```

Enter directory:

``` bash
cd blink
```

Initial structure:

``` bash
blink/
├── CMakeLists.txt
└── main/
    ├── CMakeLists.txt
    └── blink.c
```

## Code

``` c
#include <stdio.h>
#include <stdbool.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include "driver/gpio.h"
#include "esp_log.h"
#include "led_strip.h"
#include "sdkconfig.h"

static const char *TAG = "blink";

#define BLINK_GPIO CONFIG_BLINK_GPIO

static uint8_t s_led_state = 0;

#ifdef CONFIG_BLINK_LED_STRIP
    static led_strip_handle_t led_strip;

    static void blink_led(void) {
        if (s_led_state) {
            led_strip_set_pixel(led_strip, 0, 16, 16, 16);
            led_strip_refresh(led_strip);
        } else {
            led_strip_clear(led_strip);
        }
    }

    static void configure_led(void) {
        ESP_LOGI(TAG, "Configuref to blink addressable LED");
        led_strip_config_t strip_config = {
            .strip_gpio_num = BLINK_GPIO,
            .flags,with_dma = true
        };

        #if CONFIG_BLINK_LED_STRIP_BACKEND_RMT
            led_strip_rmt_config_t rmt_config = {
                .resolution_hz = 10 * 1000 * 1000,
                .flags.with_dma = false
            };
            ESP_ERROR_CHECK(led_strip_new_rmt_device(&strip_config, &rmt_config, &led_strip));
        #elif CONFIG_BLINK_LED_STRIP_BACKEND_SPI
            led_strip_spi_config_t spi_config = {
                .spi_bus = SPI2_HOST,
                .flags.with_dma = true
            };
            ESP_ERROR_CHECK(led_strip_new_spi_device(&strip_config, &spi_config, &led_strip));
        #else
        #error "unsupported LED strip backend"
        #endif 

        led_strip_clear(led_strip);
    }
#elif CONFIG_BLINK_LED_GPIO
    static void configure_led(void) {
        gpio_reset_pin(BLINK_GPIO);
        gpio_set_direction(BLINK_GPIO, GPIO_MODE_OUTPUT);
    }

    static void blink_led(void) {
        gpio_set_level(BLINK_GPIO, s_led_state);
    }
#else
#error "unsupported LED type"
#endif 

void app_main(void) {
    configure_led();

    while (1) {
        ESP_LOGI(TAG, "Turning the LED %s!", s_led_state == true ? "ON": "OFF");
        blink_led();
        s_led_state = !s_led_state;
        vTaskDelay(CONFIG_BLINK_PERIOD/portTICK_PERIOD_MS);
    }
}
```

### Explanation

This is a typical **ESP-IDF Blink LED example**, but it is more advanced than a simple GPIO blink because it supports **two types of LEDs**:

1. **Addressable LED strip** (WS2812 / NeoPixel type)
2. **Normal GPIO LED** (on/off LED)

The code uses **compile-time configuration** (`sdkconfig`) to decide which implementation gets compiled.

#### Header files

```c
#include <stdio.h>
#include <stdbool.h>
```

Standard C libraries.

##### `stdio.h`

Provides standard input/output functions:

``` c
printf()
```

ESP-IDF often uses its own logging system instead:

``` c
ESP_LOGI()
```

so this is not actually used here.

##### `stdbool.h`

Allows use of:

``` c
bool
true
false
```

Example:

``` c
bool led_on = true;
```

Instead of:

``` c
int led_on = 1;
```

##### FreeRTOS headers

``` c
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
```

ESP-IDF runs on **FreeRTOS**.

FreeRTOS provides:

* tasks
* delays
* scheduling
* synchronization

This line:

``` c
vTaskDelay()
```

comes from:

``` c
freertos/task.h
```

Example:

``` c
vTaskDelay(1000 / portTICK_PERIOD_MS);
```

means:

> Pause this task for 1000 milliseconds.

##### GPIO driver

``` c
#include "driver/gpio.h"
```

Provides ESP32 GPIO control.

Functions used:

``` c
gpio_reset_pin()
gpio_set_direction()
gpio_set_level()
```

Example:

``` c
gpio_set_level(GPIO_NUM_2, 1);
```

sets GPIO 2 HIGH.

#### Logging

``` c
#include "esp_log.h"
```

ESP-IDF logging system.

Instead of:

``` c
printf("LED ON");
```

ESP-IDF uses:

``` c
ESP_LOGI(TAG,"LED ON");
```

Output:

``` bash
I (1234) blink: LED ON
```

The format:

``` bash
LEVEL (time) TAG: message
```

##### LED strip driver

``` c
#include "led_strip.h"
```

This is for addressable LEDs.

Example:

* WS2812B
* NeoPixel
* SK6812

These LEDs are not simple ON/OFF.

They receive data:

``` bash
ESP32
 |
 | single wire
 |
WS2812
 |
RGB LED
```

You send:

``` c
red = 16
green = 16
blue = 16
```

and the LED generates that color.

##### ESP-IDF configuration

``` c
#include "sdkconfig.h"
```

This includes settings generated by:

``` bash
idf.py menuconfig
```

Example:

``` bash
CONFIG_BLINK_GPIO=2
CONFIG_BLINK_PERIOD=1000
CONFIG_BLINK_LED_GPIO=y
```

After compiling, these become C macros.

Example:

``` c
#define BLINK_GPIO CONFIG_BLINK_GPIO
```

becomes:

``` c
#define BLINK_GPIO 2
```

#### Global variables

##### Logging tag

``` c
static const char *TAG = "blink";
```

Used here:

``` c
ESP_LOGI(TAG,"...");
```

`static` means this variable is only visible inside this file.

##### LED GPIO

``` c
#define BLINK_GPIO CONFIG_BLINK_GPIO
```

Instead of hardcoding:

``` c
#define BLINK_GPIO 2
```

ESP-IDF lets you configure it.

Example:

``` bash
menuconfig
      |
      v
CONFIG_BLINK_GPIO=2
      |
      v
BLINK_GPIO
```

#### LED state

``` c
static uint8_t s_led_state = 0;
```

Stores current LED state.

Initially:

``` bash
s_led_state = 0
```

meaning:

``` bash
OFF
```

Later:

``` c
s_led_state = !s_led_state;
```

toggles:

``` bash
0 -> 1
1 -> 0
```

#### Compile-time decision

This is the important part:

``` c
#ifdef CONFIG_BLINK_LED_STRIP
```

means:

"If addressable LED support is enabled, compile this section."

Otherwise:

``` c
#elif CONFIG_BLINK_LED_GPIO
```

compile GPIO version.

Otherwise:

``` c
#error "unsupported LED type"
```

stop compilation.

##### Case 1: Addressable LED

``` c
#ifdef CONFIG_BLINK_LED_STRIP
```

Example:

WS2812 LED.

##### LED object

``` c
static led_strip_handle_t led_strip;
```

This stores the LED strip driver instance.

Think:

``` bash
led_strip
    |
    +-- GPIO
    +-- protocol
    +-- buffer
```

#### Blink function

``` c
static void blink_led(void)
```

Controls the LED.

##### Turn ON

``` c
if (s_led_state)
```

If state = 1:

``` c
led_strip_set_pixel(led_strip, 0, 16, 16, 16);
```

Arguments:

``` bash
LED index
      |
      v
      0
```

RGB:

``` bash
R = 16
G = 16
B = 16
```

So:

``` bash
white dim light
```

Then:

``` c
led_strip_refresh()
```

actually sends the data.

###### Turn OFF

``` c
led_strip_clear(led_strip);
```

sets all LEDs:

``` bash
RGB = 0,0,0
```

##### Case 2: Normal GPIO LED

``` c
#elif CONFIG_BLINK_LED_GPIO
```

This is the simple one.

###### Configure GPIO

``` c
static void configure_led(void) {
    gpio_reset_pin(BLINK_GPIO);
    gpio_set_direction(
        BLINK_GPIO,
        GPIO_MODE_OUTPUT
    );
}
```

Meaning:

Reset GPIO:

``` bash
GPIO2
 |
 reset
```

Then:

``` bash
GPIO2 = OUTPUT
```

because we want to drive the LED.

###### Blink GPIO

``` c
static void blink_led(void) {
    gpio_set_level(
        BLINK_GPIO,
        s_led_state
    );
}
```

If:

``` c
s_led_state = 1
```

then:

``` bash
GPIO2 = HIGH
LED ON
```

If:

``` c
s_led_state = 0
```

then:

``` bash
GPIO2 = LOW
LED OFF
```

#### app_main()

This is the ESP-IDF equivalent of:

``` c
main()
```

in normal C.

ESP-IDF starts FreeRTOS first, then calls:

``` c
app_main()
```

##### Configure LED

``` c
configure_led();
```

Depending on config:

Either:

``` bash
GPIO setup
```

or:

``` bash
LED strip driver setup
```

##### Infinite loop

``` c
while(1)
```

Embedded systems usually run forever.

##### Print status

``` c
ESP_LOGI(TAG, "Turning the LED %s!", s_led_state == true ? "ON":"OFF");
```

This uses the ternary operator:

Equivalent:

``` c
if(s_led_state) {
    print("ON");
} else {
    print("OFF");
}
```

##### Blink

``` c
blink_led();
```

Actually changes hardware.

##### Toggle state

``` c
s_led_state = !s_led_state;
```

Example:

Before:

``` bash
s_led_state = 0
```

After:

``` bash
s_led_state = 1
```

Next loop:

``` bash
1 -> 0
```

###### Delay

``` c
vTaskDelay(
CONFIG_BLINK_PERIOD / portTICK_PERIOD_MS
);
```

Example:

``` bash
CONFIG_BLINK_PERIOD = 1000
```

wait:

``` bash
1000 ms = 1 second
```

## Overall execution flow

``` bash
ESP32 Boot
    |
    v
FreeRTOS starts
    |
    v
app_main()
    |
    v
configure_led()
    |
    +----------------+
    |                |
 GPIO LED       LED Strip
    |                |
    v                v
set GPIO       setup driver
output         RMT/SPI
    |
    v
while(1)
    |
    v
LED ON
    |
    v
wait
    |
    v
LED OFF
    |
    v
wait
    |
    v
repeat
```

Your firmware will likely follow the simpler pattern:

``` bash
app_main()
 |
 +-- initialize drivers
 |
 +-- initialize WiFi
 |
 +-- initialize sensors
 |
 +-- create FreeRTOS tasks
 |
 +-- forever
       |
       +-- read sensor
       +-- process data
       +-- send MQTT
```

This blink example is basically showing the **ESP-IDF architecture pattern**: initialize hardware → run tasks forever.

### Why using Preprocessor

The preprocessor runs **before compilation**. It modifies your source code based on conditions or substitutions.

For example:

```c
#define BLINK_GPIO CONFIG_BLINK_GPIO
```

If `CONFIG_BLINK_GPIO` is `2`, the compiler effectively sees:

``` c
#define BLINK_GPIO 2
```

No variable is created; it's just text replacement.

#### Conditional compilation

``` c
#ifdef CONFIG_BLINK_LED_GPIO
    // GPIO implementation
#elif CONFIG_BLINK_LED_STRIP
    // LED strip implementation
#else
#error "unsupported LED type"
#endif
```

Only **one** branch is compiled.

Suppose `sdkconfig` contains:

``` c
#define CONFIG_BLINK_LED_GPIO 1
```

The compiler effectively sees:

``` c
// GPIO implementation
```

The LED strip code is completely ignored—it isn't even compiled.

#### Why not use `if`

Imagine writing:

``` c
if (led_type == GPIO) {
    gpio_set_level(...);
} else {
    led_strip_refresh(...);
}
```

The compiler would have to compile **both** implementations.

On a microcontroller:

* More flash memory used
* Larger firmware
* Longer compile time
* Unnecessary dependencies

Using the preprocessor removes unused code entirely.

### Why use pointers

A pointer stores the **memory address** of something.

Example:

``` c
int x = 10;
int *p = &x;
```

Memory:

``` bash
Address      Value

0x1000 ----> 10
              ^
              |
              p
```

`p` doesn't store `10`; it stores where `10` lives.

#### Why ESP-IDF uses pointers

Look at:

``` c
static led_strip_handle_t led_strip;
```

This is a handle (internally it's essentially a pointer to a driver object).

Later:

``` c
ESP_ERROR_CHECK(
    led_strip_new_rmt_device(
        &strip_config,
        &rmt_config,
        &led_strip
    )
);
```

Notice the `&`.

You're passing the **address** of `led_strip`.

The function can then write into that variable:

``` bash
Before

led_strip
+------+
| NULL |
+------+

        |
        | function
        v

After

led_strip
+-----------+
| 0x3FFB100 |
+-----------+
```

Now `led_strip` refers to an initialized driver object.

Without pointers, the function couldn't modify the caller's variable directly.

#### Another example

Suppose you have:

``` c
void set(int x) {
    x = 100;
}
```

Calling:

``` c
int value = 5;
set(value);
```

does **not** change `value`, because `x` is a copy.

With a pointer:

``` c
void set(int *x) {
    *x = 100;
}
```

Calling:

``` c
set(&value);
```

changes the original variable.

### Why use `struct`

A struct groups related information into one object.

Without a struct:

``` c
int gpio;
bool dma;
int resolution;
```

You now have three separate variables that belong together.

Instead:

``` c
typedef struct {
    int gpio;
    bool dma;
    int resolution;
} config_t;
```

Now:

``` c
config_t cfg;
```

contains everything.

#### In ESP-IDF

Example:

``` c
led_strip_config_t strip_config = {
    .strip_gpio_num = BLINK_GPIO,
    .flags.with_dma = true
};
```

Think of it as:

``` bash
strip_config

+----------------------+
| strip_gpio_num = 2   |
+----------------------+
| flags                |
|   with_dma = true    |
+----------------------+
```

The driver receives one configuration object instead of many separate arguments.

Imagine if the function looked like this:

``` c
led_strip_new(
    gpio,
    dma,
    resolution,
    brightness,
    pixel_count,
    backend,
    invert,
    ...
);
```

That quickly becomes hard to read and maintain.

Instead:

``` c
led_strip_new(&strip_config);
```

The configuration can grow over time without changing the function signature.

#### Why the `.` operator?

You access struct members with `.`:

``` c
strip_config.strip_gpio_num = 2;
```

Meaning:

``` bash
strip_config
      |
      +-- strip_gpio_num
```

#### Why `.member = value`?

ESP-IDF often initializes structs like this:

``` c
led_strip_config_t cfg = {
    .strip_gpio_num = 2,
    .flags.with_dma = true
};
```

These are **designated initializers**.

Compared to:

``` c
led_strip_config_t cfg = {2, true};
```

the designated version is much clearer because you immediately know what each value represents.

### How they work together

In the blink example, all three features complement each other:

``` bash
sdkconfig
    │
    ▼
Preprocessor (#ifdef)
    │
    ▼
Select GPIO or LED strip implementation
    │
    ▼
Create configuration struct
    │
    ▼
Pass the struct's address (pointer)
    │
    ▼
Driver initializes the hardware
```

This combination is one of the reasons C remains the dominant language for embedded systems: the preprocessor allows compile-time customization, structs organize related configuration cleanly, and pointers let functions efficiently work with hardware resources and large data structures without unnecessary copying.

## Project Migration to main.c

The default generated project referenced:

``` bash
main/blink.c
```

However, ESP-IDF applications require an entry function:

```c
void app_main(void)
```

The source file was renamed:

``` bash
blink.c
    |
    v
main.c
```

Updated:

``` bash
main/CMakeLists.txt
```

from:

``` cmake
idf_component_register(SRCS "blink.c")
```

to:

``` cmake
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
)
```

## Build System Verification

First build:

``` bash
idf.py build
```

The project successfully generated:

* bootloader
* partition table
* application ELF

However, linking failed:

``` bash
undefined reference to `app_main'
```

## Issue: Missing app_main

### Error

``` bash
undefined reference to app_main
```

### Cause

ESP-IDF FreeRTOS startup calls:

``` c
app_main()
```

but the compiled source did not contain this function.

### Solution

Added:

``` c
void app_main(void) {}
```

to:

``` bash
main/main.c
```

After rebuilding:

``` bash
idf.py build
```

The linker error was resolved.

## Issue: Missing Source File

### Error

``` bash
Cannot find source file:

main/blink.c
```

### Cause

CMake still referenced the old filename.

### Solution

Updated:

``` bash
main/CMakeLists.txt
```

with:

``` cmake
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
)
```

Then cleaned CMake cache:

``` bash
idf.py fullclean
```

Rebuilt:

``` bash
idf.py build
```

## LED Blink Implementation

Initial example used ESP-IDF configurable LED abstraction:

``` c
CONFIG_BLINK_LED_GPIO
CONFIG_BLINK_LED_STRIP
CONFIG_BLINK_PERIOD
```

These values are generated from:

``` bash
sdkconfig
```

through:

``` bash
idf.py menuconfig
```

## Issue: Unsupported LED Type

### Error

``` bash
#error "unsupported LED type"
```

and:

```bash
CONFIG_BLINK_PERIOD undeclared
```

### Cause

The example expected menuconfig options that were not enabled.

The code contained:

``` c
#if CONFIG_BLINK_LED_GPIO

#elif CONFIG_BLINK_LED_STRIP

#else
#error "unsupported LED type"
#endif
```

No LED type was selected.

### Solution: Simplify GPIO Control

For the first SmartDB firmware prototype, the configurable example was replaced with direct GPIO control.

Implemented:

``` c
gpio_reset_pin()
gpio_set_direction()
gpio_set_level()
```

This removes dependency on:

``` bash
CONFIG_BLINK_*
```

and creates a simpler firmware base.

## Final Firmware Structure

``` bash
blink/

├── CMakeLists.txt
├── sdkconfig
└── main/
    ├── CMakeLists.txt
    └── main.c
...
```

## Build Workflow

### Development cycle

After modifying code:

```bash
idf.py build
```

Flash:

```bash
idf.py -p /dev/ttyUSB0 flash
```

Monitor:

```bash
idf.py -p /dev/ttyUSB0 monitor
```

Combined:

``` bash
idf.py build flash monitor
```

## Hardware Connection

Find ESP32 device:

``` bash
ls /dev/ttyUSB*
```

Example:

``` bash
/dev/ttyUSB0
```

If permission denied:

``` bash
sudo usermod -aG dialout $USER
```

Restart session.

## Clean Build

If CMake cache becomes corrupted:

```bash
idf.py fullclean
idf.py build
```
