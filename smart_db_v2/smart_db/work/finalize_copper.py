"""Incremental route exchange and ground stitching, preserving existing copper."""
import os,sys,json
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parent.parent;WORK=ROOT/'work'
b=pcbnew.LoadBoard(str(ROOT/'smart_db.kicad_pcb'));mode=sys.argv[1]
codes={p.GetNetname():p.GetNetCode() for f in b.GetFootprints() for p in f.Pads()}
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
if mode=='export':
    for t in b.GetTracks():t.SetLocked(True)
    assert pcbnew.ExportSpecctraDSN(b,str(WORK/'finish_source.dsn'))
    print('exported');sys.exit(0)
if mode=='import':
    for t in b.GetTracks():t.SetLocked(True)
    assert pcbnew.ImportSpecctraSES(b,str(WORK/'finish.ses'))
elif mode=='reset_access':
    f=next(f for f in b.GetFootprints() if f.GetReference()=='R13')
    f.SetPosition(pt(73,70))
    points=[(74,70),(75.1625,70),(76,70.8375)]
    for a,c in zip(points,points[1:]):
        t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(pcbnew.F_Cu)
        t.SetWidth(pcbnew.FromMM(.3));t.SetNetCode(codes['EN']);b.Add(t)
elif mode=='signals':
    for job in json.loads((WORK/'final_route_plan.json').read_text()):
        paths=job.get('paths') or [{'layer':'F.Cu','points':p,'width':.2} for p in job['front']]+[{'layer':'B.Cu','points':job['back'],'width':.3}]
        for path in paths:
            layer=pcbnew.F_Cu if path['layer']=='F.Cu' else pcbnew.B_Cu;points=path['points']
            for a,c in zip(points,points[1:]):
                t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(layer)
                t.SetWidth(pcbnew.FromMM(path['width']));t.SetNetCode(codes[job['net']]);b.Add(t)
        for x,y in job['vias']:
            v=pcbnew.PCB_VIA(b);v.SetPosition(pt(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
            v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNetCode(codes[job['net']]);b.Add(v)
elif mode=='ground':
    for job in json.loads((WORK/'final_ground_plan.json').read_text()):
        for a,c in zip(job['front'],job['front'][1:]):
            t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(pcbnew.F_Cu)
            t.SetWidth(pcbnew.FromMM(.2));t.SetNetCode(codes['BGND']);b.Add(t)
        v=pcbnew.PCB_VIA(b);v.SetPosition(pt(*job['via']));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3))
        v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNetCode(codes['BGND']);b.Add(v)
else:raise SystemExit('export | import | ground')
b.BuildConnectivity();filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones());pcbnew.SaveBoard(str(ROOT/'smart_db.kicad_pcb'),b)
print(mode,'saved',flush=True);os._exit(0)
