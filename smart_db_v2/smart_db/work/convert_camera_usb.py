"""One-shot conversion of the camera's JST power connector to USB-A.

Retains all copper and placements predating the camera addition. Do not replay.
"""
import copy
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import *

board=parse(ROOT/'smart_db.kicad_pcb'); sch=parse(ROOT/'smart_db.kicad_sch')
old=next(f for f in children(board,'footprint') if props(f)['Reference']=='J6')
assert old[1].startswith('Connector_JST:'), 'Conversion already applied'
backup=ROOT/'work/before_camera_usb'; backup.mkdir(exist_ok=False)
for name in ['smart_db.kicad_pcb','smart_db.kicad_sch','smart_db.kicad_pro','smart_db.step','README.md']:
    shutil.copy2(ROOT/name,backup/name)
for name in ['validation_current.json','drc_routing_current.json','erc_current.json','camera_power_review.json','positions.json']:
    shutil.copy2(ROOT/'work'/name,backup/name)

sym=next(s for s in children(sch,'symbol') if props(s)['Reference']=='J6')
lib=first(sch,'lib_symbols')
d=copy.deepcopy(next(s for s in children(parse(SYMBOLS/'Connector.kicad_sym'),'symbol') if s[1]=='USB_A'))
d[1]=Quoted('Connector:USB_A');lib.append(d)
put(sym,'lib_id',Quoted(d[1]))
fp_id='Connector_USB:USB_A_TE_292303-7_Horizontal'
for key,val in [('Value','CAM USB 5V OUT'),('Footprint',fp_id),('Datasheet','https://www.te.com/en/product-292303-7.html'),('Description','TE 292303-7 USB-A socket, camera power only; data pins NC')]:prop(sym,key,val)
for p in children(sym,'property'):
    if p[1]=='Reference':put(p,'at','49.53','228.6','0')
    if p[1]=='Value':put(p,'at','49.53','231.14','0')
sym[:]=[c for c in sym if not(isinstance(c,list) and c and c[0]=='pin')]
for p in pins(d):sym.append(['pin',Quoted(value(p,'number')),['uuid',uid()]])
# Remove only the two short wires and labels belonging to the former J6.
removed=0
for item in list(sch):
    if not isinstance(item,list):continue
    if item[0]=='wire':
        match=all(48.25<float(p[1])<50.81 and 240.02<float(p[2])<242.58 for p in first(item,'pts')[1:])
    elif item[0]=='global_label':
        a=first(item,'at');match=abs(float(a[1])-48.26)<.001 and any(abs(float(a[2])-y)<.001 for y in [240.03,242.57])
    else:match=False
    if match:sch.remove(item);removed+=1
assert removed==4
connect(sch,sym,d,{'1':'LOGIC_5V_FUSED','2':None,'3':None,'4':'BGND','SH':'BGND'})
for t in children(sch,'text'):
    if str(t[1]).startswith('J6: camera POWER ONLY'):
        t[1]=Quoted('J6 USB-A: camera 5V POWER OUT. D-/D+ NC; GND and shell to BGND.\nUSB-A to micro-USB cable powers external ESP32-CAM-MB base. Wi-Fi image transfer requires firmware.\nShared F1 1.5A fuse; camera/base budget 0.5A, total target <=1.1A at 25C; verify at temperature.')

f=parse(FOOTPRINTS/'Connector_USB.pretty/USB_A_TE_292303-7_Horizontal.kicad_mod')
f[1]=Quoted(fp_id)
f[:]=[c for c in f if not(isinstance(c,list) and c and c[0] in ['version','generator','generator_version'])]
put(f,'uuid',value(old,'uuid'));put(f,'at','103','119','0')
for key in ['path','sheetname','sheetfile']:put(f,key,value(old,key))
for key in ['Reference','Value','Datasheet','Description']:
    p=prop(f,key,props(sym)[key])
    if first(p,'at') is None:put(p,'at','0','0','0')
    if first(p,'layer') is None:put(p,'layer',Quoted('F.Fab'))
    if first(p,'effects') is None:put(p,'effects',['font',['size','1','1'],['thickness','.15']])
    put(p,'hide','yes')
mapping={'1':'LOGIC_5V_FUSED','2':'unconnected-(J6-D--Pad2)','3':'unconnected-(J6-D+-Pad3)','4':'BGND','SH':'BGND'}
for pad in children(f,'pad'):
    put(pad,'net',Quoted(mapping[pad[1]]));put(pad,'uuid',uid())
    put(pad,'pinfunction',Quoted({'1':'VBUS','2':'D-','3':'D+','4':'GND','SH':'Shield'}[pad[1]]))
    put(pad,'pintype',Quoted('bidirectional+no_connect' if pad[1] in ['2','3'] else 'passive'))
board.remove(old);board.append(f)
# Only remove the camera branch; the pre-camera board remains untouched.
baseline=parse(ROOT/'work/before_camera_power/smart_db.kicad_pcb')
for kind in ['segment','via']:
    original={value(c,'uuid') for c in children(baseline,kind)}
    for c in children(board,kind):
        if value(c,'uuid') not in original:board.remove(c)
for ref,x,y in [('C25',99.5,107.5),('C26',102.5,107.5)]:
    cap=next(c for c in children(board,'footprint') if props(c)['Reference']==ref)
    put(cap,'at',num(x),num(y),'90')

# Shrink and move the logo into the free area left of the USB socket.
for p in children(board,'gr_poly'):
    if value(p,'layer')=='F.SilkS':
        pts=first(p,'pts')[1:]
        assert all(72.4<float(v[1])<99.6 and 100.2<float(v[2])<120.2 for v in pts)
        for v in pts:v[1:]=[num(68.5+(float(v[1])-72.5)*.85),num(102.5+(float(v[2])-100.3)*.85)]
for t in children(board,'gr_text'):
    if t[1] in ['J6 CAM 5V','1 GND\n2 +5V','J6 CAM / 1 GND / 2 +5V','C25','C26']:board.remove(t)
def label(text,x,y,back=False):
    e=['effects',['font',['size','.8','.8'],['thickness','.13']]]
    if back:e.append(['justify','mirror'])
    board.append(['gr_text',Quoted(text),['at',num(x),num(y),'0'],['layer',Quoted('B.SilkS' if back else 'F.SilkS')],['uuid',uid()],e])
label('J6 CAM 5V OUT',103,103.8)
label('POWER ONLY',103,105.2)
label('C25',96.5,107.5);label('C26',105.5,107.5)
label('1 +5V',96.6,110.3);label('4 GND',108.8,110.3)
label('J6 CAM 5V OUT\n1 +5V / 4 GND\n2,3 NC / SH GND',103,121,True)
def track(net,width,layer,points):
    for a,b in zip(points,points[1:]):
        board.append(['segment',['start',*[num(v) for v in a]],['end',*[num(v) for v in b]],['width',num(width)],['layer',Quoted(layer)],['net',Quoted(net)],['uuid',uid()]])
def via(net,x,y):
    board.append(['via',['at',num(x),num(y)],['size','.8'],['drill','.4'],['layers',Quoted('F.Cu'),Quoted('B.Cu')],['net',Quoted(net)],['uuid',uid()]])
power='LOGIC_5V_FUSED'
track(power,.75,'F.Cu',[(140.7875,107),(142,107),(143,107)])
for x in [142,143]:via(power,x,107)
track(power,1,'B.Cu',[(142,107),(143,107),(144.3,108.3),(144.3,122),(143.3,123),(100.5,123),(99.5,122),(99.5,110)])
# Paired vias near USB VBUS, and short local bypass connections.
for y in [109.5,110.5]:via(power,99.5,y)
track(power,1,'B.Cu',[(99.5,109.5),(99.5,110.5)])
track(power,.75,'F.Cu',[(99.5,108.45),(99.5,109.5),(99.5,110.5),(99.5,112.62)])
track(power,.6,'F.Cu',[(102.5,108.275),(102.5,109.5),(99.5,109.5)])
for x,y in [(99.5,106.55),(102.5,106.725)]:
    track('BGND',.6,'F.Cu',[(x,y),(x,105.9)]);via('BGND',x,105.9)
track('BGND',.75,'F.Cu',[(106.5,112.62),(106.5,110.5),(106.5,109.5)])
for y in [109.5,110.5]:via('BGND',106.5,y)
save(ROOT/'smart_db.kicad_sch',sch);save(ROOT/'smart_db.kicad_pcb',board)
print('Converted J6 to USB-A and rerouted camera power. Refill and verify before use.')
