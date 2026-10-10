# ByteLab

ByteLab is a related **Linux desktop workspace for ESP-IDF firmware development**, built
with Flutter. It provides project editing, native ESP-IDF builds/flashing, serial monitoring
and protocol inspection. SmartDB uses it as a development companion; SmartDB's runtime
protection and firmware do not depend on ByteLab.

Project: [ByteLab repository](https://github.com/c-lydia/ByteLab). Hosted browser edition:
[ByteLab Web](https://bytelab-web.vercel.app).
This guide reflects the local `ByteLab/bytelab` README and implementation reviewed on
2026-10-10. Consult ByteLab's own README for its full installation and development guide.

## Browser edition

The hosted web app imports an independent copy of a project folder, edits source, keeps
browser drafts and exports a project ZIP. Web Serial is available in supporting browsers
such as Chrome/Edge over HTTPS, after explicit device selection. It can inspect board logs
and send text commands, but the browser edition does not run a local ESP-IDF build/flash
toolchain. Export source and use the SmartDB setup menu or desktop tools for those tasks.
The imported copy does not overwrite the original files; clearing browser data can remove
drafts, so export work you want to retain. Desktop-only editor integrations remain separate.

## Available features and SmartDB fit

| ByteLab feature | Current use with SmartDB |
|---|---|
| Project browser and source/configuration editors | Open `SmartDB/esp_idf/smartdb_fusion` and edit the firmware project |
| Embedded Neovim | Edit with your installed Neovim and existing plugins, or choose the built-in editor |
| Build, reconfigure, size and flash controls | Run native `idf.py`; PlatformIO environment selection is not integrated |
| Serial monitor | Read SmartDB boot logs and USB JSON replies at 115200 baud |
| Protocol page | Send an exact `SMARTDB ` JSON line using text mode and LF/CRLF |
| Telemetry charts | Parse ESP-IDF `telemetry: key=value,...` logs; SmartDB's JSON/status format needs an adapter |
| Documentation page | Search SDK/chip-matched references and local examples; full references open in a browser |

ByteLab currently has no SmartDB HTTP client, fused-image viewer or dedicated configuration
screen. Use SmartDB's setup TUI for provisioning and its browser viewer/Postman requests for
HTTP inspection. Its built-in `STATUS?`, `PING` and `HELP` shortcuts belong to ByteLab's
starter firmware; SmartDB expects the JSON protocol below.

## Install and open the project

For the Linux release, extract the entire ByteLab bundle and run `./bytelab`. Keep `lib/`
and `data/` beside the executable. Flutter is not required to run that bundle. ByteLab's
current release is for x86-64 Linux; its README records Windows build instructions and
remaining Windows workflow limitations.

1. Open ByteLab's **Project** page and select `SmartDB/esp_idf/smartdb_fusion`.
2. Choose the built-in editor, or install Neovim and configure **Settings → Editor and plugins**.
3. Save source edits before building or switching projects.
4. Run SmartDB's `./setup.sh` from a terminal in that firmware folder for configuration,
   PlatformIO build and flashing. The menu selects `smartdb_s3` or `esp32cam` for the board.

ByteLab's **Settings → ESP-IDF export.sh** configures its native `idf.py` launcher. It does
not make those buttons consume `platformio.ini`. Until a PlatformIO adapter exists, use
the SmartDB setup menu to preserve this project's target, SDK defaults and dependency setup.
You can use ByteLab's serial tools without configuring an ESP-IDF toolchain.

## Inspect a SmartDB board over USB

1. Connect S3 through J4 USB-C, or connect the ESP32-CAM programmer base directly to the
   computer. The main board's J6 camera connector supplies power only.
2. Close the SmartDB setup tool and other serial monitors so the port is available.
3. In ByteLab, select the board's serial device and **115200 baud**, then connect.
4. Set the text line ending to **LF** or **CRLF**. Open **Protocol**, choose **Text**, and send:

```text
SMARTDB {"id":"bytelab-1","op":"info"}
```

Open **Monitor** to read the `SMARTDB ` response with matching `id: "bytelab-1"` and
`ok: true`. It reports board type, protocol version, IP address and active settings with
secrets redacted. S3 also reports local protection status. An empty IP means it is offline;
the USB connection still works.

For the S3's applied protection limits, send:

```text
SMARTDB {"id":"bytelab-2","op":"read_control"}
```

Use the [USB protocol reference](../api/usb.md) for every operation, field and error.
Use the TUI for credential changes so passwords/tokens are not entered into ByteLab's
retained serial history. Disconnect ByteLab before returning to setup or flashing; it
releases its own monitor for its own flash actions, but cannot coordinate another process.

## Telemetry integration boundary

ByteLab's current parser recognizes ESP-IDF lines such as:

```text
I (1200) telemetry: ram=84.5,temp=28.2,current=350
```

This is a ByteLab parser example, not output emitted by SmartDB. ByteLab interprets
`current` in **mA**, while SmartDB's JSON `current` and `current_a` fields use **A**.
Any adapter must multiply amperes by 1000 and preserve null/stale/synthetic indicators.
An ordinary serial connection does not create sensor data or feed JSON values into charts.

Future SmartDB integration would need a PlatformIO environment selector, a USB JSON
request/response adapter and an authenticated client for `/status` and `/fused.bmp`.
Those are integration tasks, not capabilities added by this documentation update. The
[local HTTP reference](../api/http.md) and [telemetry contract](../api/telemetry.md) define
the interfaces such an implementation should use.

## ByteLab source map

Paths are within the ByteLab Flutter project (`ByteLab/bytelab` locally).

| Source | Responsibility |
|---|---|
| `lib/app/app_controller.dart` | Coordinates project, build, flash and serial actions; currently selects `idf.py` |
| `lib/service/build_service.dart` | Runs the SDK process, streams output, tracks progress and cancels jobs |
| `lib/service/serial_service.dart` | Port lifecycle, log framing, serial commands and parsed metric streams |
| `lib/service/telemetry_sample.dart`, `metric_registry.dart` | Parses numeric log metrics and assigns display units |
| `lib/service/documentation_service.dart` | Detects SDK/chip metadata and assembles documentation references |
| `lib/service/neovim_service.dart` | Manages embedded Neovim sessions |
| `lib/screens/tool_pages.dart` | Protocol sender and diagnostics UI |

ByteLab settings live in `$XDG_CONFIG_HOME/bytelab/settings.json` or
`~/.config/bytelab/settings.json`; `BYTELAB_CONFIG_DIR` overrides the directory. These are
desktop preferences. Board connection settings belong to SmartDB NVS and its private setup
profile; changing ByteLab preferences does not provision board Wi-Fi.
