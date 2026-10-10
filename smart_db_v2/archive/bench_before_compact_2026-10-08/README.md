> Archived previous bench revision. The current project is [../../smart_db/](../../smart_db/README.md).

# SmartDB v2 — low-voltage bench revision

Updated 2026-10-08. **Bench prototype, not a manufacturing release. No mains connection.**
The agreed immediate target is a low-voltage test load, rather than household protection.

Open [`smart_db/smart_db.kicad_pro`](smart_db/smart_db.kicad_pro) in KiCad 10.
Editable sources: [schematic](smart_db/smart_db.kicad_sch) and
[PCB](smart_db/smart_db.kicad_pcb). The local `SmartDB.kicad_sym` and `sym-lib-table`
must remain beside the project. [Schematic PDF](smart_db_schem_v2.pdf) and
[layout preview](review/bench_layout.pdf) reflect this revision. Old Gerbers/BOM/CPL
do not represent it; no new fabrication release has been generated.

## Connections and scope

| Connector | Connection | Limit / purpose |
|---|---|---|
| J2 pin 1 / pin 2 | Ground / regulated +5 V | Logic and relay-coil supply; no raw battery or 12 V input |
| J5 pin 1 / pin 2 | LOAD_IN / LOAD_OUT | Normally-open relay contacts; provisional **5–24 V DC, up to 1 A resistive** bench envelope |
| J1 tip / sleeve | CT_HI / CT_BIAS | SCT-013-000 current-transformer input only; not a voltage input |
| J3 pins 1–4 | SDA / SCL / BGND / MCU_3V3 | 3.3 V I²C thermal sensor; see [pin map](pinmap.csv) |
| J4 | USB-C UART | Self-powered bridge; USB does not supply the board |

For the relay test, wire external supply positive → J5 pin 1 → relay → J5 pin 2 →
load positive; return the load negative directly to its supply negative. Use a
current-limited bench supply. The stated envelope is a design target, not measured
switching performance, and does not cover motors or other inductive/inrush loads.
**K1 means the relay.** Its 5 V coil controls the separate J5 contact circuit.
GPIO4/CTL high energizes K1; low/reset/power loss opens the load path. Firmware
fault detection and latched protection are not yet implemented.

The CT senses **AC**, so it cannot measure the DC load used for the relay test.
Characterize it with a separate isolated low-voltage AC test source and a verified CT.
The upstream charger, battery protection, boost converter and battery arrangement
are external system requirements, not implemented by this board.

## Applied corrections

- Replaced bare U4 with **ESP32-S3-WROOM-1-N16R8**, including its matching footprint,
  decoupling, antenna copper keepout, EN/reset and GPIO0/BOOT circuit.
  SDA uses GPIO10, SCL GPIO2; GPIO35–37 remain unused because of octal PSRAM.
- Replaced the grounded-adjustable regulator with **LDL1117S33R**, a fixed 3.3 V
  ceramic-capacitor-compatible regulator. J2's 5 V target comes from the architecture's
  documented 3.7 V-to-5 V boost output. C5/C6 and C7/C8 are input/output decoupling.
  C7 must retain at least 4.7 µF after DC-bias and temperature derating.
- Removed SW1, which was a momentary switch in the continuous power feed. Disconnect
  power at J2. F1/F2 remain explicit fuse-selection items; their ratings are not approved.
- Rebuilt CP2102N with VDD/VREGIN at 3.3 V, grounded decoupling, a 1k reset pullup,
  and USB VBUS → 22.1k → sense → 47.5k → ground. UART LEDs no longer load TX/RX.
  D7 now uses the correct SOT-143 symbol/footprint: ground is **pin 1**.
- Replaced the 12 V Songle relay with **G5LE-1 DC5** and the old driver with AO3400A.
  Removed U2/R5; added R28 gate pulldown, coil decoupling C19/C20 and J5.
  D1 cathode connects to +5 V; anode connects to the MOSFET drain/coil-low node.
  K1 pin 4 (NC contact) is unused. Neither contact is tied to CT, ground or logic power.
- Rebuilt the ADC input around CT_BIAS = VCC/2, an **18-ohm 1% 0.25 W burden**,
  1k input resistors, 220nF differential filtering and BAT54S input clamps.
  For the assumed 100 A:50 mA CT, the burden produces 0.9 Vrms / 1.27 V peak at
  nominal full scale. Verify the actual sensor, calibrate at 50/60 Hz and test overload
  and power-off behavior. ADC setup: address 0x48, differential AIN0–AIN1,
  ±2.048 V PGA range, 860 SPS. This does not establish high-frequency arc detection.
- D6 now has the matching **SMLVN6RGB1U1** six-pin symbol/footprint, with all cathodes
  grounded; GPIO6/7/8 remain active-high R/G/B. Q2 has corrected source/drain wiring
  and a gate pulldown. The exact 3.3 V buzzer still needs selection.
- Restored damaged pad stacks, replaced BOOT/RESET footprints with C&K KMR2
  (KMR221NG LFS, without ground pin), fixed overlaps and silkscreen, and closed the
  outline around J4's manufacturer cutout. Preserved the module antenna keepout.
- Removed obsolete copper and rerouted the revised netlist. Explicit net classes use
  0.4 mm power/ground, 0.75 mm supply/coil, and 1.0 mm load traces; signals and short
  fine-pitch power escapes use 0.2 mm.
- The revised PCB uses **four copper layers**: F.Cu, In1.Cu, In2.Cu and B.Cu.
  In1 has a ground pour, In2 a 3.3 V pour, with signal routing also present on these
  layers. Outer ground pours and a front VCC copper area with vias spread regulator
  heat. The module antenna keepout applies to all four copper layers.
  This changes the fabrication stack-up and cost from the original two-layer board.
  Specify a matched four-layer stack-up before fabrication; USB impedance is not validated.

## Validation

ERC: **0 errors / 0 warnings**. PCB DRC: **0 errors / 0 warnings**, **0 unconnected items**, **0 schematic/PCB mismatches**.

See [ERC](review/erc_bench.json), [DRC](review/drc_bench.json),
[pin/net assertions](review/bench_connections.json) and [netlist](review/bench_netlist.xml).
KiCad 10.0.6 checks include schematic parity. Routing used local Freerouting 2.5.0
followed by KiCad verification. ERC/DRC severities and exclusion lists were not weakened.
The PCB process constraints now permit 0.2 mm drilled holes for the module's standard
thermal pads and the CP2102N exposed-pad ground via, 0.2 mm hole-to-copper clearance and 0.25 mm routed-edge clearance,
based on [JLCPCB's published capabilities](https://jlcpcb.com/capabilities/pcb-capabilities/).
Select a process supporting these dimensions, including any small-hole charges, and
review via-in-pad filling/capping or solder-wicking control with the assembler.
These low-voltage rules do not specify mains creepage or clearance.

Historical reports remain in `review/`: original ERC 65 errors/2 warnings, original
DRC 49 errors/73 warnings plus 88 unconnected items; intermediate module migration
ERC 25 errors/1 warning, DRC 39 errors/44 warnings plus 127 unconnected items.
Only the `*_bench.json` reports describe the current revision.

## Assembly and remaining release work

U4's assembly candidate is Espressif **ESP32-S3-WROOM-1-N16R8**, JLCPCB
[C2913202](https://jlcpcb.com/partdetail/ESP32-S3-WROOM-1-N16R8/C2913202), previously
listed as Standard PCBA with X-ray inspection. Recheck stock, suffix and assembly
eligibility before ordering. The user's ESP32-WROOM-32 development board is separate.
The relay and other replacement parts still require a matched, available assembly BOM.

Before ordering: select F1/F2 and the buzzer; verify capacitor derating, regulator
thermal performance, USB layout, RF keepout and connector mechanics; review the
finished layout and exact manufacturer parts. LDO dissipation is approximately
(5−3.3) × logic current: 0.85 W at 500 mA. Copper area and ambient temperature must
be evaluated; the 1.2 A component rating is not an approved board current rating.
Bench-test power-up, UART programming, CT calibration and relay release under reset,
brownout and power loss. A rule-check pass is not a hardware test.

To enter the UART bootloader, hold BOOT/SW2, press and release RESET/SW3, then release
BOOT. Use ESP-IDF target `esp32s3`. Existing ESP32-CAM firmware is a separate camera
node, not v2 sensing or protection firmware. See the [architecture](../../../docs/architecture_full_v1.1.md)
for the unimplemented system-level protection requirements.

## Component references

- [Espressif module](https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf)
- [ST LDL1117](https://www.st.com/resource/en/datasheet/ldl1117.pdf)
- [Silicon Labs CP2102N](https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf)
- [Omron G5LE](https://omronfs.omron.com/en_US/ecb/products/pdf/en-g5le.pdf)
- [AOS AO3400A](https://www.aosmd.com/res/data_sheets/AO3400A.pdf)
- [TI ADS1115](https://www.ti.com/lit/ds/symlink/ads1115.pdf)
- [Nexperia BAT54S](https://assets.nexperia.com/documents/data-sheet/BAT54S.pdf)
- [ROHM SMLVN6RGB1U1](https://www.rohm.com/products/led/chip-leds-multi-color-type/smlvn6rgb1u-product)
