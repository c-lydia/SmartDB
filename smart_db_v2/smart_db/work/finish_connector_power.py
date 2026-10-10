"""Add reviewed wide supply branches and remove isolated, unused ground copper."""
import json
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parent.parent
b=pcbnew.LoadBoard(str(ROOT/'smart_db.kicad_pcb'))
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def track(points,layer=pcbnew.F_Cu,width=.4):
    for a,c in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(width));t.SetNetCode(b.FindNet('VCC').GetNetCode());b.Add(t)
def via(x,y):
    v=pcbnew.PCB_VIA(b);v.SetPosition(pt(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
    v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(b.FindNet('VCC').GetNetCode());b.Add(v)
for x,y in [(79.075,86.3),(73.1,62.3),(74,62.3),(145,74),(119,118)]:via(x,y)
track([(119,117),(119,118)],width=.6)
track([(119,117),(119,118)],pcbnew.B_Cu,.6)
track([(73.0875,61),(73.1,62.3),(74,62.3)])
track([(73.1,62.3),(74,62.3)],pcbnew.B_Cu,.6)
track([(146,73),(145,74)])
for path in json.loads((ROOT/'work/power_paths.json').read_text()):track(path,pcbnew.B_Cu,.6)
for z in b.Zones():
    if not z.GetIsRuleArea():z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
b.BuildConnectivity();filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones());pcbnew.SaveBoard(str(ROOT/'smart_db.kicad_pcb'),b)
print('Added 0.6 mm supply branches, paired MCU feed vias and refilled ground planes.')
