# Workflow for ESP-IDF

## Enter your project

``` bash
cd ~/projects/SmartDB/esp_idf/blink
```

## Load ESP-IDF environment (if not already loaded)

``` bash
. ~/esp/esp-idf/export.sh
```

## Configure project (optional)

``` bash
idf.py menuconfig
```

## Build

``` bash
idf.py build
```

## Find ESP32 serial port

``` bash
ls /dev/ttyUSB*
```

or:

``` bash
ls /dev/ttyACM*
```

Example:

``` bash
/dev/ttyUSB0
```

## Flash firmware

``` bash
idf.py -p /dev/ttyUSB0 flash
```

## Monitor serial output

``` bash
idf.py -p /dev/ttyUSB0 monitor
```

Exit monitor:

``` bash
Ctrl + ]
```

## Normal development loop

After changing code:

```bash
idf.py build flash monitor
```

This does:

1. Compile
2. Upload to ESP32
3. Open serial monitor

## CMake errors

Clean:

``` bash
idf.py fullclean
idf.py build
```

## Before committing to Git

Don't commit build files:

```bash
git status
```

You should **not** see:

``` bash
build/
sdkconfig.old
```

Typical ESP-IDF repo:

``` bash
blink/
├── CMakeLists.txt
├── sdkconfig
├── main/
│   ├── CMakeLists.txt
│   └── main.c
└── .gitignore
```

For SmartDB ESP32 nodes, the usual loop will become:

```bash
idf.py build flash monitor
```
