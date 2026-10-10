"""Route USB as a paired path over the back ground reference, with short breakouts.

Builds from the preserved placement-stage board. Review before rerunning: it
replaces the routing candidate, not arbitrary later hand edits.
"""
from pathlib import Path
import shutil
import pcbnew
ROOT=Path(__file__).resolve().parent.parent
# Load under the real project name so KiCad uses its existing fabrication rules.
shutil.copy2(ROOT/'work/before_connector_routing.kicad_pcb',ROOT/'smart_db.kicad_pcb')
shutil.copy2(ROOT/'work/pin_access_backup/smart_db.kicad_pro',ROOT/'smart_db.kicad_pro')
b=pcbnew.LoadBoard(str(ROOT/'smart_db.kicad_pcb'))
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
footprints={f.GetReference():f for f in b.GetFootprints()}
footprints['D7'].SetPosition(pt(71.5,81))
def track(net,points,layer=pcbnew.F_Cu,width=.2):
    for a,c in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(width));t.SetNetCode(b.FindNet(net).GetNetCode());t.SetLocked(True);b.Add(t)
def via(net,x,y):
    v=pcbnew.PCB_VIA(b);v.SetPosition(pt(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
    v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu)
    v.SetNetCode(b.FindNet(net).GetNetCode());v.SetLocked(True);b.Add(v)

# Join the reversible USB-C duplicates within the connector breakout region.
for y in [82.75,83.75]:
    track('USB_D+',[(66.46,y),(65.15,y)]);via('USB_D+',65.15,y)
track('USB_D+',[(65.15,83.75),(65.15,82.75),(65.75,82.15),(68.6,82.15),(69.2,82.75),(78.95,82.75),(79.2,82.5)],pcbnew.B_Cu)
track('USB_D-',[(66.46,82.25),(67.4,82.25),(68.2,83.05),(68.2,83.5)])
track('USB_D-',[(66.46,83.25),(67.95,83.25),(68.2,83.5)])
via('USB_D-',68.2,83.5)
track('USB_D-',[(68.2,83.5),(68.5,83.5),(68.75,83.25),(78.45,83.25),(79.2,84)],pcbnew.B_Cu)
# Fine-pitch bridge fan-in, with equal layer transitions on the main pair.
via('USB_D+',79.2,82.5);via('USB_D-',79.2,84)
track('USB_D+',[(79.2,82.5),(79.7,83),(80.55,83)])
track('USB_D-',[(79.2,84),(79.7,83.5),(80.55,83.5)])
# ESD device moved toward the connector. Each clamp branch is short.
track('USB_D+',[(70.5,81.95),(69.6,81.95)]);via('USB_D+',69.6,81.95)
track('USB_D+',[(69.6,81.95),(69.6,82.75)],pcbnew.B_Cu)
track('USB_D-',[(72.5,81.95),(72.5,83.8)]);via('USB_D-',72.5,83.8)
track('USB_D-',[(72.5,83.8),(72.5,83.25)],pcbnew.B_Cu)
track('BGND',[(70.5,80.25),(70.5,79.2)],width=.4);via('BGND',70.5,79.2)
for x,y in [(65.2,80.75),(65.2,85.25),(77,84.7),(81.5,87),(84,84)]:via('BGND',x,y)
# Explicit 0.2 mm escapes at the bridge power pads, widening immediately.
track('VCC',[(80.55,84),(80.05,84),(79.4,84.65),(79.075,84.65),(79.075,85.2)])
track('VCC',[(80.55,84.5),(80.55,85.2),(79.075,85.2)])
track('VCC',[(79.075,85.2),(79.075,87.7)],width=.4)
# I2C escape to B.Cu avoids the dense indicator/reset area near the module.
track('SDA',[(83.825,66.5),(83.825,67.5),(84.1,67.775)])
via('SDA',84.1,67.775)
b.BuildConnectivity();filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones())
pcbnew.SaveBoard(str(ROOT/'smart_db.kicad_pcb'),b)
print('Placed near-connector ESD and routed the USB pair with explicit breakouts.')
