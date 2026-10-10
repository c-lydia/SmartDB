"""Add the proposal logo and functional silk labels; safe to rerun.

Run with ordinary Python. All generated objects have deterministic UUIDs, so
rerunning replaces only these objects and preserves unrelated board graphics.
"""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "work" / "helpers" / "module_update"))
from cad_edit import Quoted as Q, children, first, parse, save, value

path = ROOT / "smart_db.kicad_pcb"
board = parse(path)
objects = []


def identifier(name):
    return Q(str(uuid.uuid5(uuid.NAMESPACE_URL, "smartdb:compact:silk:" + name)))


def text(name, label, x, y, size=1, back=False):
    effects = ["effects", ["font", ["size", str(size), str(size)], ["thickness", "0.15"]]]
    if back:
        effects.append(["justify", "mirror"])
    objects.append(["gr_text", Q(label), ["at", str(x), str(y), "0"],
                    ["layer", Q("B.SilkS" if back else "F.SilkS")],
                    ["uuid", identifier(name)], effects])


# Preserve the extracted logo's negative spaces with filled, contiguous rectangles.
for i, (x, y, xx, yy) in enumerate(json.loads((ROOT / "work" / "logo_rects.json").read_text())):
    pts = [["xy", f"{72 + a * .1:.4f}", f"{100 + c * .1:.4f}"]
           for a, c in [(x, y), (xx, y), (xx, yy), (x, yy)]]
    objects.append(["gr_poly", ["pts", *pts], ["stroke", ["width", "0"], ["type", "solid"]],
                    ["fill", "yes"], ["layer", Q("F.SilkS")], ["uuid", identifier(f"logo-{i}")]])

text("revision", "COMPACT v2", 86, 122.5)
text("bench", "LOW VOLTAGE BENCH ONLY", 113, 50.5, .9)
text("boot", "BOOT", 104, 59.8)
text("reset", "RESET", 105, 75)
text("ct", "J1  CT INPUT", 130, 48.5, .9)
text("i2c", "J3  I2C", 66.5, 59, .9)
text("usb", "USB UART", 64, 94, .9)
text("load", "J5 LOAD", 149.5, 85, .9)
text("input", "J2 5V IN", 146, 118.5, .9)
text("status", "STATUS", 87, 69.2, .8)
text("power", "3V3", 114, 117.5, .8)
text("usbpower", "USB 3V3", 93, 97.5, .8)

# Pin labels on the reverse remain visible when the right-angle connectors are fitted.
for pin, label, y in [(4, "4 3V3", 64.38), (3, "3 GND", 66.92),
                      (2, "2 SCL", 69.46), (1, "1 SDA", 72)]:
    text(f"i2c-pin-{pin}", label, 69.2, y, .9, back=True)
    text(f"i2c-front-pin-{pin}", label, 69.2, y, .9)
text("i2c-back", "J3 I2C / 3.3V", 68, 58.5, 1, back=True)
text("j2-plus", "2 +5V", 141, 109, 1, back=True)
text("j2-gnd", "1 GND", 141, 114, 1, back=True)
text("j5-out", "2 OUT", 141, 89, 1, back=True)
text("j5-in", "1 IN", 141, 94, 1, back=True)
text("j5-back", "J5 RELAY / N.O.", 137, 82, 1, back=True)
text("j2-back", "J2 REGULATED 5V", 138, 104, 1, back=True)
text("ct-back", "J1 SCT-013-000 ONLY\nTIP: CT_HI / SLEEVE: CT_BIAS", 132, 66, 1, back=True)
text("usb-back", "J4 USB UART\nSELF-POWERED / NO USB SUPPLY", 95, 86, 1, back=True)
text("prototype-back", "SMARTDB COMPACT v2\nLOW VOLTAGE BENCH PROTOTYPE", 106, 105, 1.2, back=True)

# A readable front legend supplements the terminal-adjacent underside markings.
text("terminal-legend", "J2: 1 GND / 2 +5V\nJ5: 1 IN / 2 OUT", 112, 55, .9)
for ref, label, x, y in [
    ('TP1', '+5V', 136, 105.8), ('TP2', '3V3', 119, 114.7),
    ('TP3', 'MCU 3V3', 69, 55), ('TP4', 'ADC 3V3', 148, 68.5),
    ('TP5', 'GND', 119, 123.4),
]:
    text('testpoint-' + ref, label, x, y, .8)

ids = {value(n, "uuid") for n in objects}
board[:] = [n for n in board if not isinstance(n, list) or value(n, "uuid") not in ids]
board.extend(objects)
save(path, board)
print(f"Added {len(objects)} logo and label objects.")
