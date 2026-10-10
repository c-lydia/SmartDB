# C interfaces

These listings come directly from the firmware headers whenever the website is rebuilt.
See the [code guide](index.md) for module ownership and the [HTTP](../api/http.md) and
[USB](../api/usb.md) references for interfaces used outside the firmware process.

## Fusion core

`fc_thermal_t` carries native samples and validity/correction masks. Timestamps are local
monotonic microseconds. `fc_calibration_t` holds the row-major RGB-to-thermal homography;
`fc_measure()` computes native-sample region statistics independently of rendering.

```{literalinclude} ../../esp_idf/smartdb_fusion/components/fusion_core/include/fusion_core.h
:language: c
:linenos:
```

## Protection core

`pc_update()` evaluates configuration, sensor freshness, thresholds and re-arm conditions.
GPIO output and persistence belong to `system_control.c`, allowing the state machine and
RMS implementation to run in host tests.

```{literalinclude} ../../esp_idf/smartdb_fusion/components/fusion_core/include/protection.h
:language: c
:linenos:
```

## System control

The HTTP handlers and USB dispatcher share `system_config_apply()`. `system_request_open()`
de-energizes the relay; it does not clear a trip or authorize closing.

```{literalinclude} ../../esp_idf/smartdb_fusion/main/system_control.h
:language: c
:linenos:
```

## Connection settings

`device_settings()` returns immutable settings for the current boot. A successful save
persists a complete replacement; callers must restart before it becomes active.
`device_settings_public()` returns an owned cJSON object with secret values redacted.

```{literalinclude} ../../esp_idf/smartdb_fusion/main/device_settings.h
:language: c
:linenos:
```

## Telemetry publisher

The snapshot callback returns heap-allocated JSON. The publisher takes ownership and frees
it after acceptance or queue eviction. See [telemetry delivery](../api/telemetry.md).

```{literalinclude} ../../esp_idf/smartdb_fusion/main/telemetry.h
:language: c
:linenos:
```
