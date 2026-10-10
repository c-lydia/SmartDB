"""Staged full-board routing. 'critical' rebuilds from full_routing_backup.

Engineering work record: do not replay critical/import over subsequent hand edits.
Uses the real project stem to preserve the project's design rules.
"""
from pathlib import Path
import json
import os
import shutil
import sys
import pcbnew

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / 'work'
mode = sys.argv[1]
if mode == 'critical':
    shutil.copy2(WORK/'full_routing_backup/smart_db.kicad_pcb', ROOT/'smart_db.kicad_pcb')
if mode == 'import':
    shutil.copy2(WORK/'critical_before_import.kicad_pcb', ROOT/'smart_db.kicad_pcb')
b = pcbnew.LoadBoard(str(ROOT/'smart_db.kicad_pcb'))
net_codes = {p.GetNetname(): p.GetNetCode() for f in b.GetFootprints() for p in f.Pads()}
def pt(x,y): return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def track(net, points, width=.2, layer=pcbnew.F_Cu):
    for a,c in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(layer)
        t.SetWidth(pcbnew.FromMM(width));t.SetNetCode(net_codes[net])
        t.SetLocked(True);b.Add(t)
def via(net,x,y):
    v=pcbnew.PCB_VIA(b);v.SetPosition(pt(x,y));v.SetWidth(pcbnew.FromMM(.6))
    v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetNetCode(net_codes[net])
    v.SetLocked(True);b.Add(v)
if mode == 'critical':
    # Replace the earlier buck output chain: load current must not traverse FB.
    for t in list(b.GetTracks()):
        if isinstance(t,pcbnew.PCB_VIA): continue
        a,c=t.GetStart(),t.GetEnd()
        if (t.GetNetname()=='VCC' and t.GetLayer()==pcbnew.F_Cu
            and min(a.x,c.x)>=pcbnew.FromMM(119) and min(a.y,c.y)>=pcbnew.FromMM(108)
            and not (a.x==c.x==pcbnew.FromMM(119))): b.Remove(t)
    # Short, front-layer switch and bootstrap routes.
    track('BUCK_SW',[(128.1375,113),(130.75,113)],.6)
    track('BUCK_SW',[(130.275,109),(130.75,109.475),(130.75,113)],.4)
    track('BUCK_BST',[(128.1375,112.05),(128.725,111.4625),(128.725,109)])
    # Local input capacitor feeds VIN directly; EN branches from VIN.
    track('LOGIC_5V_FUSED',[(125.525,116.5),(125.525,114.2875),(125.8625,113.95)],.6)
    track('LOGIC_5V_FUSED',[(125.8625,113.95),(125.8625,113)],.4)
    track('LOGIC_5V_FUSED',[(125.525,116.5),(125.525,119.5625),(125.9625,120)],.75)
    track('BGND',[(128.1375,113.95),(128.475,114.2875),(128.475,116.5)],.6)
    track('BGND',[(128.475,116.5),(128.475,119.5625),(128.0375,120)],.6)
    for x,y in [(129.3,115),(129.5,116.5),(129,120),(139.5,111.525),(139.5,116.525)]:
        via('BGND',x,y)
    track('BGND',[(128.475,115),(129.3,115)],.6)
    track('BGND',[(128.475,116.5),(129.5,116.5)],.6)
    track('BGND',[(128.0375,120),(129,120)],.6)
    track('BGND',[(138,111.525),(139.5,111.525)],.6)
    track('BGND',[(138,116.525),(139.5,116.525)],.6)
    # Output capacitors first, wide load branch second, dedicated FB sense third.
    track('VCC',[(135.25,113),(136.725,114.475),(138,114.475)],1.0)
    track('VCC',[(138,114.475),(140,114.475),(141,115.475),(141,118.475),(140,119.475),(138,119.475)],1.0)
    track('VCC',[(138,119.475),(136.5,119.475)],.8)
    for x,y in [(136.5,119.475),(136.5,120.275)]:via('VCC',x,y)
    track('VCC',[(136.5,119.475),(136.5,120.275)],.8)
    track('VCC',[(136.5,119.475),(135.025,118),(119,118)],1.0,pcbnew.B_Cu)
    track('VCC',[(136.5,120.275),(136.5,119.475)],.8,pcbnew.B_Cu)
    track('VCC',[(125.8625,112.05),(124.5,112.05)],.2)
    via('VCC',124.5,112.05)
    track('VCC',[(124.5,112.05),(122,114.55),(122,116.75),(123.25,118)],.2,pcbnew.B_Cu)
    # Fine-pitch ADC supply escape widens only after clearing adjacent pins.
    track('ADC_3V3',[(134.15,74),(135.6,74),(135.6,75)],.2)
    via('ADC_3V3',135.6,75)
    # Load contacts remain on outer copper, without current bottleneck vias.
    track('LOAD_IN',[(131,84),(131,87),(136,92),(147,92),(149,94)],1.0)
    track('LOAD_OUT',[(125,98.2),(125,96.5),(130.5,91),(139,91),(141,89),(149,89)],1.0,pcbnew.B_Cu)
elif mode == 'import':
    # SES omits fixed copper. Mark the exported baseline fixed in KiCad too.
    for t in b.GetTracks(): t.SetLocked(True)
    assert pcbnew.ImportSpecctraSES(b,str(WORK/'remaining.ses'))
    for t in b.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA):
            if t.GetNetname()=='ADC_3V3' and t.GetPosition()==pt(135.6,74):
                t.SetPosition(pt(135.6,75))
        elif t.GetWidth()<pcbnew.FromMM(.2): t.SetWidth(pcbnew.FromMM(.2))
    track('ADC_3V3',[(135.6,74),(135.6,75)],.2)
elif mode != 'export': raise SystemExit('critical | export | import')
if mode in ['critical','import']:
    b.BuildConnectivity();filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones())
    pcbnew.SaveBoard(str(ROOT/'smart_db.kicad_pcb'),b)
    # This KiCad SWIG build crashes while releasing mutated-board wrappers.
    # Save first; a separate kicad-cli process performs the authoritative checks.
    print(mode,'saved; verify with kicad-cli DRC',flush=True)
    os._exit(0)
if mode == 'export':
    for t in b.GetTracks(): t.SetLocked(True)
    assert pcbnew.ExportSpecctraDSN(b,str(WORK/'remaining_source.dsn'))
    pads=[]
    for f in b.GetFootprints():
        for p in f.Pads():
            pads.append({'ref':f.GetReference(),'pin':p.GetNumber(),'net':p.GetNetname(),
                         'xy':[pcbnew.ToMM(p.GetPosition().x),pcbnew.ToMM(p.GetPosition().y)]})
    (WORK/'pads_current.json').write_text(json.dumps(pads,indent=2))
assert all(isinstance(t,pcbnew.PCB_VIA) or t.GetLayer() in [pcbnew.F_Cu,pcbnew.B_Cu] for t in b.GetTracks())
print(mode,'complete;',len(list(b.GetTracks())),'copper items')
