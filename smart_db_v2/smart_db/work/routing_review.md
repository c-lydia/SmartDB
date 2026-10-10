# Completed routing review — 2026-10-10

All connections are routed in the permanent v2 project. KiCad 10.0.6 reports
**0 DRC violations, 0 unconnected items, 0 schematic parity issues and 0 ERC
violations**. This is a routed low-voltage prototype; fabrication review and
hardware qualification remain.

## Construction and trace widths

Working specification: four-layer, 1.6 mm FR-4, 1 oz outer copper and 0.5 oz inner
copper. Layer order is signal/power–ground–ground–signal/power. CAD specifies four
layers and 1.6 mm thickness; exact dielectric dimensions will follow the selected
fabricator. These are common options, consistent with [JLCPCB's copper guide](https://jlcpcb.com/help/article/jlcpcb-copper-weight).

There is no universal electronics trace width. [IPC-2152's published scope](https://www.ipc.org/TOC/IPC-2152.pdf)
relates conductor dimensions to current and allowable temperature rise. This
review follows that principle; it does not claim an IPC-2152 thermal calculation
or certification. [JLCPCB's fabrication limits](https://jlcpcb.com/capabilities/pcb-capabilities/)
are finer than this board's retained 0.20 mm minimum track width.

The request for wider routes is reflected in both copper and netclass preferences:

| Circuit | Preferred width | Actual treatment |
|---|---:|---|
| Ordinary signals | 0.30 mm | Widened where clearance permits; 0.20–0.25 mm in remaining tight channels and escapes |
| 3.3 V power and ground branches | 0.60 mm | Main distribution widened; local pad/congestion neckdowns retained |
| 5 V input/fused supply and relay coil | 0.75 mm | Wide supply routes with local pad escapes |
| Relay load contacts | 1.00 mm | At least 1.00 mm throughout, no vias |
| USB D+/D− | 0.20 mm | Existing pair retained pending impedance review |

Some narrower sections are longer than individual pad escapes because adjacent
routes form tight channels. Exact widths, counts and lengths are recorded in
[validation_current.json](validation_current.json). No clearance rule or DRC
exclusion was relaxed. Final copper has 608 segments and 88 vias.

## Power and returns

The buck switch-to-inductor and bootstrap routes remain short and on F.Cu. The
input capacitor feeds VIN directly, with EN branching locally. The inductor
output feeds the output capacitors and wider distribution; a separate feedback
branch prevents load current passing through the FB pad. Ground stitching ties
input/output capacitor returns to the inner planes. The output connection and
MCU feed use parallel vias.

The [AP63203 layout guidance](https://www.diodes.com/datasheet/download/AP63200-AP63201-AP63203-AP63205.pdf)
emphasizes close input bypassing and thermal ground connections and recommends
2 oz outer copper for its 2 A case. This selected 1 oz board is **not rated here
for 2 A continuous output**. Verify load budget, voltage drop, R29, fuse
coordination, temperature rise, radio-burst droop and load-step response.
Wider copper alone does not establish a current rating.

Relay contact routes use separate outer layers without vias. The ADC region
remains separated from the bottom-right buck converter and uses the R30/C3/C4
supply filter. New stitches connect the ADC, clamp diode, decoupling and MCU
ground regions. Both inner layers remain ground with no signal tracks. Analog
layout considerations were checked against [ADS1115 guidance](https://www.ti.com/lit/ds/symlink/ads1115.pdf);
noise and accuracy still need measurement.

R13 moved from (76, 73.3) to (73, 70) mm to open its reset routing path. The green
LED uses four layer transitions to cross existing channels while retaining a
0.30 mm main run.

## USB integrity

The main USB pair remains on B.Cu over In2.Cu ground, with 0.20 mm traces and
0.30 mm edge gap in its parallel section. Each main connector-to-bridge path
changes layers twice. Both reversible USB-C contacts are joined; ESD protection
remains near the connector with a nearby ground via.

[Silicon Labs AN0046](https://www.silabs.com/documents/public/application-notes/an0046-efm32-usb-hardware-design-guidelines.pdf)
specifies a 90 Ω differential routing target. These dimensions have **not** been
established as 90 Ω for a manufacturer's stackup. Widening USB arbitrarily would
not validate it. The [CP2102N](https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf)
uses full-speed USB. Planar measurements, excluding via barrels, are:

| Path | Length | Layer transitions |
|---|---:|---:|
| J4 A6 → U5 D+ | 17.518 mm | 2 |
| J4 B6 → U5 D+ | 18.518 mm | 2 |
| J4 A7 → U5 D− | 14.815 mm | 2 |
| J4 B7 → U5 D− | 15.493 mm | 2 |

Contact-dependent mismatch is approximately 2.7–3.0 mm. No length-match,
impedance or eye-diagram pass is claimed. Check both plug orientations,
enumeration, UART traffic, ESD behavior and power sequencing on hardware.

## Spacing and mechanical access

Original 0.50 mm load clearance, 0.25 mm supply clearance and other project rules
are retained, along with mounting-hole keepouts and the four-layer antenna keepout.
J3 projects about 5.5 mm beyond the edge and has labels on both sides. J4 retains
the mid-mount cutout for its [Amphenol connector](https://www.amphenol-cs.com/product/12401948e412a.html).
Its local 3D model is approximate because the manufacturer's STEP download was
unavailable; verify the actual drawing, board thickness and enclosure fit.

Scope remains regulated 5 V logic and a provisional 5–24 V DC, up-to-1 A resistive
relay test load. No mains use. Thermal, relay release, USB and ADC performance
are not established by a CAD rule-check pass.

## Saved evidence

J6 now provides ESP32-CAM-MB power through a TE 292303-7 USB-A socket, with SMD
contacts and through-hole shell anchors: 1 +5V, 4 GND, SH GND, 2/3 intentionally NC.
A short USB-A to micro-USB cable powers the external camera's USB base.
Wi-Fi image transfer requires suitable firmware; the current camera firmware
is diagnostic and has no streaming server. J3 remains the thermal camera's I²C connector.
The new fused 5 V branch uses a 1 mm B.Cu trunk, 0.75 mm fuse-pad connection,
paired 0.8/0.4 mm feed and connector vias, a 0.75 mm VBUS escape and local
10 µF/100 nF bypassing. It follows the bottom edge and changes to F.Cu before
crossing the existing B.Cu VCC route. All 589 original
segments, 80 original vias and existing component placements/pads are preserved.
F1's symbol was corrected to match its specified one-time 1.5 A fast-acting part.
The USB-A socket is at (103, 117.3) mm; the logo was reduced and moved left.
Only the USB-A front-flange silkscreen was changed in the local footprint.
The manufacturer's recommended 1.42 mm board thickness differs from the selected
1.6 mm board: verify anchor retention and solderability with real parts before release.

[Littelfuse's 467 datasheet](https://www.littelfuse.com/assetdocs/fuse-467-datasheet?assetguid=4a59f034-1cca-460e-a5ba-e1e66247c76d)
requires 25% derating for continuous operation, giving 1.125 A at 25°C before
additional temperature derating; its 70°C example gives 0.90 A for this rating.
Our provisional total budget is 1.1 A at 25°C, including a 0.5 A camera/base allowance.
This requires measured confirmation and does not enlarge the board's current rating.
See [camera power review](camera_power_review.json) for cable details and checks.

- [Validation and source hashes](validation_current.json)
- [Final DRC](drc_routing_current.json) and [ERC](erc_current.json)
- [Copper PDF](routing_current.pdf), [front](routing_front_current.png),
  [back](routing_back_current.png), and [3D view](connectors_current.png)
- `routed_checkpoint/`: completed CAD backup and DRC report

Intermediate scripts, DSN/SES files and reports are engineering work records;
some rebuild or append earlier stages. Do not replay them on the final board.
Reopen the project if an older KiCad editor view is still open.
