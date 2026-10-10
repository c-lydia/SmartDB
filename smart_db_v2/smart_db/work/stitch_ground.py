"""Stitch isolated decoupling, indicator and USB-sense returns into ground planes."""
from pathlib import Path
import json
import pcbnew
ROOT=Path(__file__).resolve().parent.parent
b=pcbnew.LoadBoard(str(ROOT/'smart_db.kicad_pcb'))
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
paths=json.loads((ROOT/'work/ground_stitches.json').read_text())
for path in paths:
    for a,c in zip(path,path[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetWidth(pcbnew.FromMM(.3))
        t.SetLayer(pcbnew.F_Cu);t.SetNetCode(b.FindNet('BGND').GetNetCode());b.Add(t)
    v=pcbnew.PCB_VIA(b);v.SetPosition(pt(*path[-1]));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNetCode(b.FindNet('BGND').GetNetCode());b.Add(v)
b.BuildConnectivity();filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones());pcbnew.SaveBoard(str(ROOT/'smart_db.kicad_pcb'),b)
