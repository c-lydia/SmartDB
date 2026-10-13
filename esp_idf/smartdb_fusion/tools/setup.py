#!/usr/bin/env python3
"""Interactive SmartDB USB provisioning, configuration and PlatformIO launcher.

Only pySerial (included in PlatformIO) is needed beyond the Python standard library.
Importing this module never opens a port, writes a profile or runs PlatformIO.
"""

import getpass
import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".setup.json"
TARGETS = {"smartdb_s3": "SmartDB main board", "esp32cam": "ESP32-CAM"}
FIELDS = {
    "wifi_ssid": 32,
    "wifi_password": 63,
    "api_token": 96,
    "camera_url": 191,
    "camera_id": 63,
    "installation_id": 63,
    "telemetry_url": 255,
    "telemetry_token": 700,
}


def defaults():
    return {
        "settings": {
            "wifi_ssid": "",
            "wifi_password": "",
            "api_token": secrets.token_urlsafe(32),
            "camera_url": "http://192.168.1.50/capture",
            "camera_id": "smartdb-camera-1",
            "installation_id": "panel-1",
            "telemetry_url": "",
            "telemetry_token": "",
        },
        "devices": {},
    }


def validate_settings(settings):
    if set(settings) != set(FIELDS):
        raise ValueError("Connection settings must contain all eight fields.")
    for key, maximum in FIELDS.items():
        value = settings[key]
        if not isinstance(value, str) or len(value.encode("utf-8")) > maximum:
            raise ValueError(f"{key}: maximum {maximum} UTF-8 bytes.")
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError(f"{key}: control characters are not allowed.")
    if not settings["wifi_ssid"]:
        raise ValueError("Enter the Wi-Fi name (SSID).")
    if len(settings["wifi_password"].encode("utf-8")) < 8:
        raise ValueError("Wi-Fi password must contain 8–63 UTF-8 bytes (WPA2).")
    for key, minimum in [
        ("api_token", 24),
        ("telemetry_token", 1 if settings["telemetry_url"] else 0),
    ]:
        value = settings[key]
        if len(value) < minimum or any(not 33 <= ord(c) <= 126 for c in value):
            raise ValueError(
                f"{key}: use at least {minimum} printable ASCII characters, without spaces."
            )
    for key, scheme in [("camera_url", "http"), ("telemetry_url", "https")]:
        value = settings[key]
        if key == "telemetry_url" and not value:
            continue
        parsed = urlsplit(value)
        if (
            parsed.scheme != scheme
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or any(not 33 <= ord(c) <= 126 for c in value)
        ):
            raise ValueError(
                f"{key}: enter a {scheme}:// address without credentials or a fragment."
            )
        if parsed.port is not None and not 1 <= parsed.port <= 65535:
            raise ValueError(f"{key}: invalid port.")
    if not settings["camera_id"] or not settings["installation_id"]:
        raise ValueError("Camera and installation IDs cannot be empty.")


def load_profile(path=PROFILE):
    if not path.exists():
        return defaults()
    data = json.loads(path.read_text())
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("settings"), dict)
        or not isinstance(data.get("devices"), dict)
    ):
        raise ValueError(
            "Saved setup profile is invalid. Restore it or move it aside before continuing."
        )
    validate_settings(data["settings"])
    return data


def save_profile(data, path=PROFILE):
    validate_settings(data["settings"])
    descriptor, temporary = tempfile.mkstemp(prefix=".setup-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(data, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)  # mkstemp creates mode 0600; replacing preserves it.
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def response_from_line(line, request_id):
    marker = b"SMARTDB "
    position = line.find(marker)
    if position < 0:
        return None
    try:
        data = json.loads(line[position + len(marker) :])
    except (ValueError, UnicodeError):
        return None
    if not isinstance(data, dict) or data.get("id") != request_id:
        return None
    return data


class Device:
    def __init__(self, port, serial_factory=None):
        if serial_factory is None:
            try:
                import serial
            except ImportError as error:
                raise RuntimeError(
                    "pySerial is missing. Run setup.sh using the PlatformIO installation."
                ) from error
            serial_factory = serial.Serial
        self.serial = serial_factory(port=None, baudrate=115200, timeout=0.2, write_timeout=3)
        self.serial.dtr = False
        self.serial.rts = False
        self.serial.port = port
        self.serial.open()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.serial.close()

    def request(self, operation, data=None, timeout=6):
        request_id = secrets.token_hex(8)
        request = {"id": request_id, "op": operation}
        if data is not None:
            request["data"] = data
        encoded = (
            b"SMARTDB "
            + json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
            + b"\n"
        )
        if len(encoded) > 4096:
            raise ValueError("Settings are too large for a USB request.")
        # Never echo requests: they may contain Wi-Fi passwords or tokens.
        self.serial.write(encoded)
        self.serial.flush()
        deadline = time.monotonic() + timeout
        pending = b""
        while time.monotonic() < deadline:
            chunk = self.serial.read_until(b"\n", 8192)
            pending += chunk
            if len(pending) > 16384:
                pending = b""
            if not pending.endswith(b"\n"):
                continue
            response = response_from_line(pending, request_id)
            pending = b""
            if response is None:
                continue
            if response.get("ok") is not True:
                message = {
                    "ESP_ERR_INVALID_ARG": "The board rejected a setting. Check the field limits.",
                    "ESP_ERR_INVALID_STATE": "Configuration changed or another update is active. Read it again.",
                }
                raise RuntimeError(
                    message.get(
                        response.get("error"),
                        "The board could not save/apply the request. Check its storage.",
                    )
                )
            return response
        raise TimeoutError(
            "No setup response. Close other serial monitors, check the port, and tap RESET. Older firmware needs the initial setup-enabled flash."
        )


def check_board(info, target):
    if info.get("protocol") != 1 or info.get("board") != target:
        raise ValueError(
            f"This is not the expected {TARGETS[target]} running setup protocol 1. Select the correct board/port."
        )


def ask(label, current="", secret=False):
    hint = (
        " [Enter keeps saved value]" if secret and current else f" [{current}]" if current else ""
    )
    value = (getpass.getpass if secret else input)(label + hint + ": ")
    return value if value else current


def yes(label, default=False):
    while True:
        value = input(label + (" [Y/n]: " if default else " [y/N]: ")).strip().lower()
        if not value:
            return default
        if value in ("y", "yes", "n", "no"):
            return value in ("y", "yes")
        print("Choose y or n.")


def edit_profile(profile):
    settings = dict(profile["settings"])
    print("\nWi-Fi for both boards (2.4 GHz WPA2). Passwords are hidden.")
    settings["wifi_ssid"] = ask("Wi-Fi name", settings["wifi_ssid"])
    settings["wifi_password"] = ask("Wi-Fi password", settings["wifi_password"], secret=True)
    settings["camera_id"] = ask("Camera name", settings["camera_id"])
    settings["installation_id"] = ask("Installation name", settings["installation_id"])
    settings["camera_url"] = ask(
        "Camera capture URL (updated automatically when camera connects)", settings["camera_url"]
    )
    print("A shared camera/API token is generated automatically and reused for both boards.")
    if yes("Change the shared token? Both boards will need their settings applied again"):
        settings["api_token"] = ask(
            "New token (Enter generates one)", secret=True
        ) or secrets.token_urlsafe(32)
    if yes("Enable HTTPS telemetry uploads?", bool(settings["telemetry_url"])):
        settings["telemetry_url"] = ask("Full HTTPS telemetry URL", settings["telemetry_url"])
        settings["telemetry_token"] = ask(
            "Telemetry bearer token", settings["telemetry_token"], secret=True
        )
    else:
        settings["telemetry_url"] = ""
        settings["telemetry_token"] = ""
    validate_settings(settings)
    profile["settings"] = settings
    save_profile(profile)
    print(
        "Saved locally. Choose Set up camera / Set up main board to apply these settings over USB."
    )


def choose_port(profile, target):
    try:
        from serial.tools import list_ports
    except ImportError as error:
        raise RuntimeError(
            "pySerial is missing; use setup.sh with PlatformIO installed."
        ) from error
    ports = list(list_ports.comports())
    print(f"\nConnect {TARGETS[target]} by USB. Close its serial monitor.")
    for index, port in enumerate(ports, 1):
        print(f"  {index}. {port.device} — {port.description}")
    previous = profile["devices"].get(target, {}).get("port", "")
    if len(ports) == 1:
        previous = ports[0].device
    choice = ask("Port number or full port name", previous)
    if choice.isdigit() and 1 <= int(choice) <= len(ports):
        return ports[int(choice) - 1].device
    if not choice:
        raise ValueError("No port selected. Connect a USB data cable and try again.")
    return choice


def pio_path():
    candidates = [Path(sys.executable).with_name("pio"), Path.home() / ".platformio/penv/bin/pio"]
    for path in candidates:
        if path.is_file():
            return str(path)
    found = shutil.which("pio")
    if not found:
        raise RuntimeError(
            "Install the PlatformIO VS Code extension first; its build tools were not found."
        )
    return found


def build(target, port=None):
    if target not in TARGETS and target != "smartdb_s3_demo":
        raise ValueError("Unknown firmware target.")
    command = [pio_path(), "run", "-e", target]
    if port:
        command += ["-t", "upload", "--upload-port", port]
    print("\nBuilding" + (" and flashing" if port else "") + f" {target}…")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise RuntimeError(
            "Build/upload failed. The PlatformIO output above gives the cause; settings were not applied."
        )


def wait_info(device, target, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            info = device.request("info", timeout=2)
            check_board(info, target)
            return info
        except TimeoutError:
            time.sleep(0.25)
    raise TimeoutError(
        "The board did not restart into setup firmware. Release BOOT/IO0 and tap RESET, then retry."
    )


def provision(profile, target):
    try:
        validate_settings(profile["settings"])
    except ValueError:
        edit_profile(profile)
    port = choose_port(profile, target)
    try:
        with Device(port) as device:
            info = device.request("info", timeout=4)
            check_board(info, target)
    except TimeoutError:
        if not yes(f"Install setup-enabled firmware on {TARGETS[target]} now?", True):
            return
        build(target, port)
        time.sleep(2)
    with Device(port) as device:
        info = wait_info(device, target)
        print(f"Connected: {TARGETS[target]} ({info['device_id']}).")
        settings = dict(profile["settings"])
        if target == "esp32cam":
            settings["telemetry_url"] = ""
            settings["telemetry_token"] = ""
        device.request("save_settings", settings)
        print("Settings saved on the board. Restarting to join Wi-Fi; relay stays open.")
        device.request("restart")
        time.sleep(1)
        info = wait_info(device, target)
        deadline = time.monotonic() + 25
        while not info.get("ip") and time.monotonic() < deadline:
            time.sleep(1)
            info = device.request("info")
            check_board(info, target)
    profile["devices"][target] = {
        "port": port,
        "ip": info.get("ip", ""),
        "device_id": info["device_id"],
    }
    if info.get("ip"):
        print(f"Wi-Fi connected: {info['ip']}")
        if target == "esp32cam":
            profile["settings"]["camera_url"] = f"http://{info['ip']}/capture"
            print(
                "Camera address updated. Apply settings to the main board next; reserve this camera IP in your router."
            )
    else:
        print(
            "Settings saved, but Wi-Fi has not connected yet. Check SSID/password and the 2.4 GHz network; USB setup still works."
        )
    save_profile(profile)


def control_config(current, amperes, temperature, scale, commissioned):
    values = [float(amperes), float(temperature), float(scale)]
    if not all(math.isfinite(v) for v in values) or not (
        0 < values[0] <= 1 and 20 <= values[1] <= 100 and 50 <= values[2] <= 200
    ):
        raise ValueError(
            "Use current >0 to 1 A, temperature 20–100 °C, and current scale 50–200 A/V."
        )
    version = current["version"] + 1
    if version > 4294967295:
        raise ValueError("Configuration version is exhausted.")
    return dict(
        version=version,
        commissioned=commissioned,
        current_limit_a=values[0],
        temperature_limit_c=values[1],
        current_scale_a_per_v=values[2],
    )


def protection(profile):
    with Device(choose_port(profile, "smartdb_s3")) as device:
        check_board(device.request("info"), "smartdb_s3")
        current = device.request("read_control")["config"]
        print("\nProtection limits (saved immediately; no rebuild).")
        amperes = ask("Current trip limit, A (maximum 1)", str(current["current_limit_a"]))
        temperature = ask("Temperature trip limit, °C", str(current["temperature_limit_c"]))
        scale = ask("Calibrated current scale, A/V", str(current["current_scale_a_per_v"]))
        commissioned = yes(
            "Mark the installation commissioned? Physical re-arm is still required",
            current["commissioned"],
        )
        updated = control_config(current, amperes, temperature, scale, commissioned)
        device.request("write_control", updated)
        applied = device.request("read_control")["config"]
        if applied["version"] != updated["version"]:
            raise RuntimeError("Configuration changed during verification. Read it again.")
        print(
            f"Saved version {applied['version']}. Relay is open. Re-arm locally only when the sensors and installation are ready."
        )


def status(profile, target):
    with Device(choose_port(profile, target)) as device:
        info = device.request("info")
        check_board(info, target)
    print(json.dumps(info, indent=2))  # Firmware deliberately omits passwords/tokens.


def open_relay(profile):
    with Device(choose_port(profile, "smartdb_s3")) as device:
        check_board(device.request("info"), "smartdb_s3")
        device.request("open_relay")
    print("Relay opened. A latched trip is not cleared.")


def viewer(profile):
    ip = profile["devices"].get("smartdb_s3", {}).get("ip", "")
    if not ip:
        raise ValueError("Set up the main board first so its address is known.")
    print("Opening the local viewer. Use the shared token when prompted.")
    if yes("Show the token here so you can copy it into the viewer?"):
        print(profile["settings"]["api_token"])
    webbrowser.open(f"http://{ip}/")


def main():
    profile = load_profile()
    print("\nSmartDB setup — two boards, one menu")
    while True:
        print(
            "\n  1  Wi-Fi and connection settings\n  2  Set up ESP32-CAM (do this first)\n"
            "  3  Set up SmartDB main board\n  4  Change protection limits\n"
            "  5  Board status\n  6  Open relay\n  7  Build / update firmware\n"
            "  8  Open fused-image viewer\n  0  Exit"
        )
        choice = input("\nChoose: ").strip()
        try:
            if choice == "0":
                return
            if choice == "1":
                edit_profile(profile)
            elif choice in ("2", "3"):
                provision(profile, "esp32cam" if choice == "2" else "smartdb_s3")
            elif choice == "4":
                protection(profile)
            elif choice == "5":
                target = (
                    "esp32cam"
                    if yes("Read camera status? (No selects main board)")
                    else "smartdb_s3"
                )
                status(profile, target)
            elif choice == "6":
                open_relay(profile)
            elif choice == "7":
                target = (
                    "esp32cam"
                    if yes("Build the camera firmware? (No selects main board)")
                    else "smartdb_s3"
                )
                port = choose_port(profile, target) if yes("Flash after building?") else None
                if port:
                    try:
                        with Device(port) as device:
                            check_board(device.request("info", timeout=3), target)
                    except TimeoutError:
                        if not yes(
                            f"No setup response. Continue flashing the selected {TARGETS[target]}?"
                        ):
                            continue
                build(target, port)
            elif choice == "8":
                viewer(profile)
            else:
                print("Choose a listed number.")
        except (ValueError, RuntimeError, OSError) as error:
            print(f"\nCould not complete that step: {error}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nSetup closed.")
    except (ValueError, OSError) as error:
        print(f"Setup could not start: {error}", file=sys.stderr)
        sys.exit(1)
