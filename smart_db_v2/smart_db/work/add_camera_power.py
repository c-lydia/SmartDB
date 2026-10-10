"""Add ESP32-CAM power connector once, preserving existing copper.

Run with ordinary Python, followed by refill_camera.py in KiCad Python.
"""
import copy
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import *

sch=parse(ROOT/'smart_db.kicad_sch');board=parse(ROOT/'smart_db.kicad_pcb')
assert not any(props(s).get('Reference')=='J6' for s in children(sch,'symbol')), 'Already added'
backup=ROOT/'work/before_camera_power';backup.mkdir(exist_ok=True)
for name in ['smart_db.kicad_pcb','smart_db.kicad_sch','smart_db.kicad_pro','smart_db.step']:
    assert not (backup/name).exists(), 'Backup exists: review before replay'
    shutil.copy2(ROOT/name,backup/name)
for name in ['validation_current.json','drc_routing_current.json','erc_current.json','positions.json']:
    shutil.copy2(ROOT/'work'/name,backup/name)
lib=first(sch,'lib_symbols')
def definition(libid):
    found=next((s for s in children(lib,'symbol') if s[1]==libid),None)
    if found:return found
    library,name=libid.split(':')
    found=copy.deepcopy(next(s for s in children(parse(SYMBOLS/(library+'.kicad_sym')),'symbol') if s[1]==name))
    found[1]=Quoted(libid);lib.append(found);return found
def fresh_uuids(node):
    for c in node:
        if isinstance(c,list):
            if c and c[0]=='uuid':c[1]=uid()
            else:fresh_uuids(c)
def symbol(ref,template,libid,val,fp,x,y,mapping):
    obj=copy.deepcopy(next(s for s in children(sch,'symbol') if props(s)['Reference']==template))
    fresh_uuids(obj);put(obj,'lib_id',Quoted(libid));put(obj,'at',num(x),num(y),'0')
    d=definition(libid)
    for name,text in [('Reference',ref),('Value',val),('Footprint',fp),('Description',props(d).get('Description','')),('Datasheet',props(d).get('Datasheet',''))]:prop(obj,name,text)
    for p in children(obj,'property'):put(p,'at',num(x),num(y),'0')
    put(next(p for p in children(obj,'property') if p[1]=='Reference'),'at',num(x-4),num(y-8.5),'0')
    put(next(p for p in children(obj,'property') if p[1]=='Value'),'at',num(x-4),num(y-5.9),'0')
    for inst in children(first(obj,'instances'),'project'):
        for path in children(inst,'path'):put(path,'reference',Quoted(ref))
    obj[:]=[c for c in obj if not(isinstance(c,list) and c and c[0]=='pin')]
    for p in pins(d):obj.append(['pin',Quoted(value(p,'number')),['uuid',uid()]])
    sch.append(obj);connect(sch,obj,d,mapping)
    return obj

cfg=[('J6','J2','Connector_Generic:Conn_01x02','ESP32-CAM 5V OUT',
      'Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical',(55.88,240.03),(142.3,120,0),{'1':'BGND','2':'LOGIC_5V_FUSED'}),
     ('C25','C5','Device:C','10uF 16V X7R','Capacitor_SMD:C_0805_2012Metric',
      (119.38,240.03),(142,111.5,90),{'1':'LOGIC_5V_FUSED','2':'BGND'}),
     ('C26','C6','Device:C','100nF 16V X7R','Capacitor_SMD:C_0603_1608Metric',
      (180.34,240.03),(142.2,114.4,90),{'1':'LOGIC_5V_FUSED','2':'BGND'})]
for ref,template,libid,val,fp,schpos,pcbpos,mapping in cfg:
    sym=symbol(ref,template,libid,val,fp,*schpos,mapping)
    library,name=fp.split(':');f=parse(FOOTPRINTS/(library+'.pretty')/(name+'.kicad_mod'))
    f[1]=Quoted(fp);f[:]=[c for c in f if not(isinstance(c,list) and c and c[0] in ['version','generator','generator_version'])]
    fresh_uuids(f);put(f,'uuid',uid());put(f,'at',*[num(v) for v in pcbpos])
    put(f,'path',Quoted('/'+value(sym,'uuid')));put(f,'sheetname',Quoted('/'));put(f,'sheetfile',Quoted('smart_db.kicad_sch'))
    for key in ['Reference','Value','Datasheet','Description']:prop(f,key,props(sym)[key])
    for p in children(f,'property'):
        if first(p,'at') is None:put(p,'at','0','0','0')
        if first(p,'layer') is None:put(p,'layer',Quoted('F.Fab'))
        if first(p,'effects') is None:p.append(['effects',['font',['size','1','1'],['thickness','.15']]])
        if p[1]!='Reference':put(p,'hide','yes')
    # Labels are kept outside the connector/capacitor body areas.
    refprop=next(p for p in children(f,'property') if p[1]=='Reference')
    put(refprop,'hide','yes')
    for p in children(f,'pad'):
        if str(p[1]) in mapping:put(p,'net',Quoted(mapping[str(p[1])]))
        a=first(p,'at')
        if len(a)==3:a.append(num(pcbpos[2]))
        else:a[3]=num(float(a[3])+pcbpos[2])
    board.append(f)

# Correct the existing part's schematic type; same two passive pins and footprint.
fuse=next(s for s in children(sch,'symbol') if props(s)['Reference']=='F1')
fd=definition('Device:Fuse');old=definition('Device:Polyfuse')
assert [(value(p,'number'),first(p,'at')) for p in pins(fd)]==[(value(p,'number'),first(p,'at')) for p in pins(old)]
put(fuse,'lib_id',Quoted('Device:Fuse'))
fuseurl='https://www.littelfuse.com/assetdocs/fuse-467-datasheet?assetguid=4a59f034-1cca-460e-a5ba-e1e66247c76d'
for node in [fuse,next(f for f in children(board,'footprint') if props(f)['Reference']=='F1')]:
    prop(node,'Description','1.5 A fast-acting one-time fuse, Littelfuse 467 series')
    prop(node,'Datasheet',fuseurl)

sch.append(['text',Quoted('J6: camera POWER ONLY, 1 GND / 2 +5V. Images over Wi-Fi.\nShared F1 1.5A fuse; camera budget 0.5A, total continuous target <=1.1A at 25C; verify at temperature.'),
    ['at','18','259','0'],['effects',['font',['size','1.1','1.1']],['justify','left']],['uuid',uid()]])
def text(label,x,y,size=.8,back=False):
    effects=['effects',['font',['size',num(size),num(size)],['thickness','.13']]]
    if back:effects.append(['justify','mirror'])
    board.append(['gr_text',Quoted(label),['at',num(x),num(y),'0'],['layer',Quoted('B.SilkS' if back else 'F.SilkS')],['uuid',uid()],effects])
for t in children(board,'gr_text'):
    if t[1]=='J2 5V IN':put(t,'at','149','105.3','0')
text('J6 CAM 5V',143.2,124.15,.8)
text('1 GND\n2 +5V',133.2,122.5,.75)
text('J6 CAM / 1 GND / 2 +5V',137,123.8,.8,True)
text('C25',140.3,110.6,.65);text('C26',140.6,113,.65)

def track(net,width,layer,pts):
    for a,b in zip(pts,pts[1:]):
        board.append(['segment',['start',*[num(v) for v in a]],['end',*[num(v) for v in b]],['width',num(width)],['layer',Quoted(layer)],['net',Quoted(net)],['uuid',uid()]])
def via(net,x,y):
    board.append(['via',['at',num(x),num(y)],['size','.8'],['drill','.4'],['layers',Quoted('F.Cu'),Quoted('B.Cu')],['net',Quoted(net)],['uuid',uid()]])
# Independent branch at F1 output, avoiding the buck/relay distribution neckdowns.
power='LOGIC_5V_FUSED'
track(power,.75,'F.Cu',[(140.7875,107),(142,107),(143,107)])
for x in [142,143]:via(power,x,107)
track(power,1,'B.Cu',[(142,107),(143,107),(144.3,108.3),(144.3,120)])
for ref in ['C25','C26']:
    f=next(f for f in children(board,'footprint') if props(f)['Reference']==ref)
    x,y,angle=map(float,first(f,'at')[1:]);assert angle==90
    pads={p[1]:first(p,'at') for p in children(f,'pad')}
    py=y-float(pads['1'][1]);gy=y-float(pads['2'][1])
    track(power,.6,'F.Cu',[(x,py),(143.3,py)]);via(power,143.3,py)
    track(power,.75,'B.Cu',[(143.3,py),(144.3,py)])
    track('BGND',.6,'F.Cu',[(x,gy),(140.8,gy)]);via('BGND',140.8,gy)

save(ROOT/'smart_db.kicad_sch',sch);save(ROOT/'smart_db.kicad_pcb',board)
print('Added J6, C25, C26; corrected F1 symbol. Refill zones and run DRC/ERC.')
