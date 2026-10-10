# Protocol implementation

These source listings are refreshed on every documentation build. The
[USB protocol](../api/usb.md) and [telemetry guide](../api/telemetry.md) explain the
wire formats and client behavior; the [code guide](index.md) links the other modules.

## USB dispatcher

```{literalinclude} ../../esp_idf/smartdb_fusion/main/serial_setup.c
:language: c
:linenos:
```

## HTTPS telemetry worker

```{literalinclude} ../../esp_idf/smartdb_fusion/main/telemetry.c
:language: c
:linenos:
```
