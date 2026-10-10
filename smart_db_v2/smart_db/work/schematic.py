import sys,copy,shutil,json,hashlib
from pathlib import Path
sys.path.insert(0,'/tmp/smartdb_review/module_update')
from cad_edit import *
OUT=Path('/tmp/smartdb_review/compact');dest=OUT/BOARD.parent;dest.mkdir(parents=True,exist_ok=True)
for f in SOURCE.joinpath(BOARD.parent).iterdir():
 if f.suffix in ['.kicad_sch','.kicad_pcb','.kicad_pro','.kicad_sym'] or f.name=='sym-lib-table':shutil.copy2(f,dest/f.name)
sch=parse(OUT/BOARD.with_suffix('.kicad_sch'));originals={props(s)['Reference']:s for s in children(sch,'symbol')};lib=first(sch,'lib_symbols');defs={s[1]:s for s in children(lib,'symbol')}
# Reuse the symbol insertion helper, without running the previous revision generator.
source=Path('/tmp/smartdb_review/violations_update/fix_schematic.py').read_text()
exec(source[source.index('def library_symbol'):source.index('# Project-local symbol')])
exec(source[source.index('def place('):source.index('# Bench relay:')])
def remove(ref):
 s=originals[ref];definition=defs[value(s,'lib_id')];coords=[]
 for p in pins(definition):
  x,y,d=pin_position(s,p);r=math.radians(d)
  coords += [(round(x,4),round(y,4)),(round(x-2.54*math.cos(r),4),round(y+2.54*math.sin(r),4))]
 for n in list(sch):
  if not isinstance(n,list):continue
  if n is s:sch.remove(n);continue
  if n[0] in ['global_label','label','no_connect','junction']:
   a=first(n,'at')
   if a and tuple(round(float(v),4) for v in a[1:3]) in coords:sch.remove(n)
  elif n[0]=='wire':
   pts=first(n,'pts')[1:]
   if all(tuple(round(float(v),4) for v in p[1:3]) in coords for p in pts):sch.remove(n)
remove('U3');remove('F2')
place('U3',137.16,330.2,0,'AP63203WU-7',{'1':'VCC','2':'LOGIC_5V_FUSED','3':'LOGIC_5V_FUSED','4':'BGND','5':'BUCK_SW','6':'BUCK_BST'},'Regulator_Switching:AP63203WU')
place('R29',165.1,25.4,90,'0R 1A min',{'1':'VCC','2':'MCU_3V3'},'Device:R','Resistor_SMD:R_0805_2012Metric',template='R14')
# Replace the continuous-input PTC placeholder with a low-resistance fuse candidate.
s=originals['F1'];prop(s,'Value','046701.5NRHF 1.5A');prop(s,'Footprint','Fuse:Fuse_0603_1608Metric')
for ref,val,fp in [('C5','10uF 10V X7R','Capacitor_SMD:C_1206_3216Metric'),('C7','22uF 10V X7R','Capacitor_SMD:C_1206_3216Metric'),('C8','22uF 10V X7R','Capacitor_SMD:C_1206_3216Metric'),('C4','10uF 10V X7R','Capacitor_SMD:C_0805_2012Metric')]:
 prop(originals[ref],'Value',val);prop(originals[ref],'Footprint',fp)
place('L1',208.28,330.2,90,'6.8uH SRP5030TA-6R8M',{'1':'BUCK_SW','2':'VCC'},'Device:L','Inductor_SMD:L_Bourns_SRP5030T')
place('C21',248.92,330.2,0,'100nF 25V X7R',{'1':'BUCK_BST','2':'BUCK_SW'},'Device:C','Capacitor_SMD:C_0603_1608Metric')
place('C22',208.28,365.76,0,'100uF 10V',{'1':'LOGIC_5V_FUSED','2':'BGND'},'Device:C_Polarized','Capacitor_SMD:CP_Elec_6.3x7.7')
place('C23',289.56,330.2,0,'22uF 10V X7R',{'1':'MCU_3V3','2':'BGND'},'Device:C','Capacitor_SMD:C_1206_3216Metric')
place('C24',248.92,365.76,0,'100uF 10V',{'1':'LOGIC_5V_FUSED','2':'BGND'},'Device:C_Polarized','Capacitor_SMD:CP_Elec_6.3x7.7')
place('R30',289.56,365.76,90,'10R 1%',{'1':'VCC','2':'ADC_3V3'},'Device:R','Resistor_SMD:R_0603_1608Metric',template='R14')
# Remap only the analog front end's rail labels on its pin stubs.
for ref,pinnums in {'U1':['8'],'C3':['1'],'C4':['1'],'R3':['1'],'D9':['2'],'D10':['2']}.items():
 s=originals[ref]
 for p in pins(defs[value(s,'lib_id')]):
  if value(p,'number') not in pinnums:continue
  x,y,d=pin_position(s,p);r=math.radians(d);xy=(round(x-2.54*math.cos(r),4),round(y+2.54*math.sin(r),4))
  n=next(n for n in children(sch,'global_label') if tuple(round(float(v),4) for v in first(n,'at')[1:3])==xy)
  assert n[1]=='VCC',(ref,n);n[1]=Quoted('ADC_3V3')
place('#FLG04',330.2,365.76,0,'PWR_FLAG',{'1':'ADC_3V3'},'power:PWR_FLAG',template='#FLG01')
for i in range(4):place('H'+str(i+1),350.52+i*20.32,330.2,0,'M3 mounting',{},'Mechanical:MountingHole','MountingHole:MountingHole_3.2mm_M3',template='C9')
for i,net in enumerate(['LOGIC_5V_FUSED','VCC','MCU_3V3','ADC_3V3','BGND']):
 place('TP'+str(i+1),350.52+i*20.32,365.76,0,net,{'1':net},'Connector:TestPoint','TestPoint:TestPoint_Pad_D1.5mm',template='C9')
for n in children(sch,'text'):
 if 'Output capacitor must retain' in n[1]:n[1]=Quoted('AP63203 buck: 6.8uH shielded inductor, 2x22uF output, 100nF bootstrap. Validate load-step response.')
 if 'fuse/buzzer selection' in n[1]:n[1]=Quoted('Bench validation required: source impedance, capacitor derating, ripple, USB eye and CT noise.')
put(first(sch,'title_block'),'rev',Quoted('2-compact'))
save(OUT/BOARD.with_suffix('.kicad_sch'),sch)
print('Updated buck supply, MCU reservoir, analog filter, test points and mounting symbols.')
