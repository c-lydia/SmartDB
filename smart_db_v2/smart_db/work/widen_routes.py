"""Widen routing; preserve USB pair and use DRC to identify necessary neckdowns."""
import json,os,sys,shutil,math
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parent.parent;WORK=ROOT/'work'
mode=sys.argv[1]
if mode=='prepare':
    shutil.copy2(ROOT/'smart_db.kicad_pcb',WORK/'before_widening.kicad_pcb')
    shutil.copy2(ROOT/'smart_db.kicad_pro',WORK/'before_widening.kicad_pro')
    p=json.loads((ROOT/'smart_db.kicad_pro').read_text())
    for c in p['net_settings']['classes']:
        if c['name']=='Default':c['track_width']=.3
        if c['name']=='Power':c['track_width']=.6
    (ROOT/'smart_db.kicad_pro').write_text(json.dumps(p,indent=2)+'\n')
b=pcbnew.LoadBoard(str(ROOT/'smart_db.kicad_pcb'))
codes={p.GetNetname():p.GetNetCode() for f in b.GetFootprints() for p in f.Pads()}
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def track(net,a,c,width=.3):
    t=pcbnew.PCB_TRACK(b);t.SetStart(pt(*a));t.SetEnd(pt(*c));t.SetLayer(pcbnew.F_Cu);t.SetNetCode(codes[net]);t.SetWidth(pcbnew.FromMM(width));b.Add(t)
def via(net,x,y):
    v=pcbnew.PCB_VIA(b);v.SetPosition(pt(x,y));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetLayerPair(pcbnew.F_Cu,pcbnew.B_Cu);v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNetCode(codes[net]);b.Add(v)
if mode=='prepare':
    widths={}
    for t in list(b.GetTracks()):
        if t.GetNetname()=='LED_R_A':b.Remove(t);continue
        if t.GetNetname()=='ADC_3V3':
            if isinstance(t,pcbnew.PCB_VIA) and t.GetPosition()==pt(135.6,75):b.Remove(t);continue
            if not isinstance(t,pcbnew.PCB_VIA) and t.GetStart()==pt(135.6,74) and t.GetEnd()==pt(135.6,75):b.Remove(t);continue
        if isinstance(t,pcbnew.PCB_VIA) or t.GetNetname() in ['USB_D+','USB_D-']:continue
        widths[t.m_Uuid.AsString()]=pcbnew.ToMM(t.GetWidth())
        target=.6 if t.GetNetname() in ['VCC','MCU_3V3','ADC_3V3','BGND','BUCK_SW'] else .3
        if t.GetWidth()<pcbnew.FromMM(target):t.SetWidth(pcbnew.FromMM(target))
    (WORK/'original_track_widths.json').write_text(json.dumps(widths,indent=2))
    # Give adjacent RGB pads separate escapes before routing the longer runs.
    track('LED_B_A',(84.475,71.95),(85.7,71.95),.3);via('LED_B_A',85.7,71.95)
    track('LED_R_A',(84.475,73),(85.7,73),.3);via('LED_R_A',85.7,73)
elif mode=='spans':
    widths=json.loads((WORK/'original_track_widths.json').read_text());count=0
    for t in list(b.GetTracks()):
        if isinstance(t,pcbnew.PCB_VIA) or t.GetNetname() in ['USB_D+','USB_D-']:continue
        w=pcbnew.ToMM(t.GetWidth());length=pcbnew.ToMM(t.GetLength())
        if w>=.3 or length<=3:continue
        a=t.GetStart();c=t.GetEnd();ax,ay=pcbnew.ToMM(a.x),pcbnew.ToMM(a.y);cx,cy=pcbnew.ToMM(c.x),pcbnew.ToMM(c.y)
        u=.8/length;points=[(ax,ay),(ax+(cx-ax)*u,ay+(cy-ay)*u),(cx-(cx-ax)*u,cy-(cy-ay)*u),(cx,cy)]
        net=t.GetNetCode();layer=t.GetLayer();b.Remove(t)
        for i,(a,c) in enumerate(zip(points,points[1:])):
            seg=pcbnew.PCB_TRACK(b);seg.SetStart(pt(*a));seg.SetEnd(pt(*c));seg.SetLayer(layer);seg.SetNetCode(net);seg.SetWidth(pcbnew.FromMM(.3 if i==1 else w));b.Add(seg)
            widths[seg.m_Uuid.AsString()]=w
        count+=1
    (WORK/'original_track_widths.json').write_text(json.dumps(widths,indent=2));print('Widened',count,'long spans',flush=True)
elif mode=='neckdown':
    d=json.loads((WORK/sys.argv[2]).read_text());widths=json.loads((WORK/'original_track_widths.json').read_text())
    affected={x['uuid'] for issue in d['violations'] if issue['type'] in ['clearance','shorting_items','solder_mask_bridge'] for x in issue['items']}
    count=0
    for t in b.GetTracks():
        if isinstance(t,pcbnew.PCB_VIA):continue
        uid=t.m_Uuid.AsString()
        if uid in affected and uid in widths and pcbnew.ToMM(t.GetWidth())>widths[uid]+.001:
            # Retain the widest intermediate size that can pass DRC.
            current=pcbnew.ToMM(t.GetWidth());w=.4 if current>.4 else .3 if current>.3 else .25 if current>.25 else .2
            t.SetWidth(pcbnew.FromMM(max(w,widths[uid])));count+=1
    print('Adjusted',count,'local widths',flush=True)
b.BuildConnectivity();filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones());pcbnew.SaveBoard(str(ROOT/'smart_db.kicad_pcb'),b)
print(mode,'saved',flush=True);os._exit(0)
