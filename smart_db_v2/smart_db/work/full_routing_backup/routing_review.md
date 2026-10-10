# Connector routing review — 2026-10-09

The I²C header and USB-to-UART networks are routed in the permanent v2 project.
This is a partially routed low-voltage prototype, not a fabrication release.

## Board construction assumption

Following the user's request for standard construction, use a four-layer,
1.6 mm FR-4 board with 1 oz outer copper and 0.5 oz inner copper as the working
manufacturing specification. This follows a common low-cost option; see
[JLCPCB's copper options](https://jlcpcb.com/quote/pcbOrderFaq/Copper%20Weight).
The CAD already specifies four copper layers and 1.6 mm overall thickness.
Layer order remains signal/power, ground, ground, signal/power. Exact dielectric
thicknesses and material properties will follow the selected manufacturer's
stackup; this specification does not establish controlled impedance.

## Signal integrity and returns

The main USB pair uses B.Cu over the In2.Cu ground plane, 0.2 mm trace width and
0.3 mm edge-to-edge spacing in its parallel section. Each main path changes
layers twice. Short connector breakouts join both reversible USB-C data contacts;
the ESD device is closer to the connector and has a nearby ground via. Inner
ground layers contain no signal tracks. Separate stitching connects the MCU
decoupling, USB sensing and indicator ground islands to these planes.

The selected [CP2102N](https://www.silabs.com/documents/public/data-sheets/cp2102n-datasheet.pdf)
uses USB full speed (12 Mbps). Planar connector-to-bridge path measurements,
excluding via barrel length, are:

| Path | Length | Layer transitions |
|---|---:|---:|
| J4 A6 → U5 D+ | 17.518 mm | 2 |
| J4 B6 → U5 D+ | 18.518 mm | 2 |
| J4 A7 → U5 D− | 14.815 mm | 2 |
| J4 B7 → U5 D− | 15.493 mm | 2 |

These are not length-matched routes: contact-dependent planar mismatch is about
2.7–3.0 mm. No impedance or eye-diagram result is claimed. The final stackup must
establish the USB differential impedance, and routing may need adjustment after
that review. Verify both plug orientations, enumeration, sustained UART traffic,
ESD performance and power sequencing on assembled hardware. I²C timing also
depends on the external sensor cable and configured bus speed.

## Power capacity

New VCC branches use 0.6 mm copper, existing distribution uses 0.4 mm, and only
the bridge's fine-pitch power escapes use 0.2 mm. The MCU feed has two parallel
0.6/0.3 mm vias. The long supply branches connect to the existing rail through
TP2's network; they are not fed through a test probe. Ground pours provide returns.

The working copper weights are specified above; allowable temperature rise,
MCU peak load and external header load have not been confirmed. Therefore these widths are provisional, not an
ampacity rating. Check voltage drop including vias, R29, connectors and the fuse;
measure ESP32 radio-burst droop and load-step response. The buck converter input,
switch/bootstrap loop and fused 5 V network remain unrouted, so the board is not
yet a working powered circuit. Existing fuse and component values are not newly
qualified by this routing pass.

## Spacing, safety and mechanical access

KiCad's existing trace, hole, edge, net-class, courtyard and antenna rules were
preserved. Minimum routed trace width is 0.2 mm. The load-net 0.5 mm clearance
and supply-net 0.25 mm clearance remain in force, and mounting-hole keepouts and
the four-layer antenna keepout are retained. The inner planes remain ground;
no new manufacturing rules or DRC exclusions were added to obtain a pass.

J3's header pins extend about 5.5 mm beyond the board, with pin labels on both
sides. J4's original cutout geometry is retained at the board edge. Its selected
[Amphenol 12401948E412A](https://www.amphenol-cs.com/product/12401948e412a.html)
is a mid-mount connector; verify board thickness and the actual connector drawing
before assembly. Its local 3D model is an approximate shell/tongue visualization
because the manufacturer's STEP download was unavailable. It cannot certify
mechanical fit. Enclosure clearance and cable strain relief remain unverified.

The scope remains a regulated 5 V logic supply and a provisional low-voltage
resistive test load. The board has no mains clearance or protection certification.
Relay/load routing, fuse coordination and relay release testing remain outstanding.

## Verification and remaining work

- ERC: 0 violations.
- DRC: 0 clearance/geometry/footprint violations; 0 schematic parity issues.
- Completed nets: SDA, SCL, RX, TX, USB_D±, USB_CC1/2, USB_RESET, USB_VBUS,
  USB_VBUS_SENSE, USB_LED_A, VCC, MCU_3V3 and BGND.
- 62 unconnected items remain on other nets, including the buck circuit,
  fused 5 V, relay/load, ADC supply/analog input, reset/boot, LEDs and buzzer.

The DRC is not an overall pass while these connections remain open. Detailed
results and source hashes are in [validation_current.json](validation_current.json).
The [routing PDF](routing_current.pdf) contains all four copper layers.
