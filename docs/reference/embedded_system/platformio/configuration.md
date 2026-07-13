# PlatformIO Configuration

## Installation

1. If haven't, install VSCode from Microsoft
2. Open VSCode, go to Extension Marketplace
3. Search for PlatformIO IDE
4. Install PlatformIO IDE

## Setup the project

1. On the left taskbar, click on PlatformIO icon
2. Under Quick Access, click Open
3. In the UI display in the text editor, click New Project
4. In the Project Wizard, input project name, choose ESP Dev Module, and choose esp-idf framework
5. Select location for the project, then click Finish
6. Now, go to file explorer, open `/src/main.c`, then paste the provided code below

``` C
/**
 * Blink
 *
 * Turns on an LED on for one second,
 * then off for one second, repeatedly.
 */
#include "Arduino.h"

// Set LED_BUILTIN if it is not defined by Arduino framework
// #define LED_BUILTIN 13

void setup() {
  // initialize LED digital pin as an output.
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  // turn the LED on (HIGH is the voltage level)
  digitalWrite(LED_BUILTIN, HIGH);

  // wait for a second
  delay(1000);

  // turn the LED off by making the voltage LOW
  digitalWrite(LED_BUILTIN, LOW);

   // wait for a second
  delay(1000);
}
```

7. Connect the board, then change baudrate to 115200

``` ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = espidf
monitor_speed = 115200
```

8. Press `ctrl + alt + b` to build the project
9.  After the build succeeds, upload the project to the ESP32 board by press `ctrl + shift + P`, then search for `PlatformIO: Upload and Monitor`

> Warning:
> - If the upload fails follow the steps below:
>   - Open terminal inside VSCode
>   - Check if the device is detected or not, using `ls -l /dev/ttyUSB*`
>   - If it is detected, check group, `groups`
>   - If it is in the wrong group, using dialout command to allow permission, `sudo usermod -aG dialout $USER`
>   - If it still won't work, change permissions using chmod command, `sudo chmod 666 /dev/ttyUSB0`
