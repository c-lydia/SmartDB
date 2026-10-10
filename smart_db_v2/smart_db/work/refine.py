import sys,json
sys.path.insert(0,'/tmp/smartdb_review/module_update')
from cad_edit import *
from pcb_edit import load_footprint,refresh_uuids
root=Path('/tmp/smartdb_review/compact');p=root/BOARD.with_suffix('.kicad_pcb');b=parse(p);sch=parse(root/BOARD.with_suffix('.kicad_sch'));syms={props(x)['Reference']:x for x in children(sch,'symbol')}
# Replace the axial flyback diode with its surface-mount 1N4007 equivalent.
s=syms['D1'];prop(s,'Value','M7 (1N4007 SMD)');prop(s,'Footprint','Diode_SMD:D_SMA')
f=next(f for f in children(b,'footprint') if props(f)['Reference']=='D1');new=load_footprint('Diode_SMD:D_SMA');refresh_uuids(new)
for key in ['uuid','at','path','sheetname','sheetfile']:n=first(f,key);put(new,key,*n[1:])
for p_ in children(new,'pad'):
 old=next(x for x in children(f,'pad') if x[1]==p_[1]);put(p_,'net',value(old,'net'));put(p_,'pinfunction',value(old,'pinfunction'));put(p_,'pintype',value(old,'pintype'))
b[b.index(f)]=new
for f in children(b,'footprint'):
 ref=props(f).get('Reference')
 if f is new:ref='D1'
 for key,v in props(syms[ref]).items():
  if key=='Footprint':continue
  q=prop(f,key,v)
  if key not in ['Reference','Value'] or key=='Value' or ref.startswith('H'):
   put(q,'at','0','0','0');put(q,'layer',Quoted('F.Fab'));put(q,'hide','yes');put(q,'effects',['font',['size','1','1'],['thickness','.15']])
   if not first(q,'uuid'):put(q,'uuid',uid())
 # Match schematic BOM inclusion, including the mechanical/testpoint symbols.
 attr=first(f,'attr')
 if attr and 'exclude_from_bom' in attr:attr.remove('exclude_from_bom')
for z in children(b,'zone'):
 if first(z,'keepout'):put(first(z,'keepout'),'pads','allowed')
save(root/BOARD.with_suffix('.kicad_sch'),sch);save(p,b)
positions=json.loads((root/'positions.json').read_text());positions.update({'J3':[71,72,180],'R24':[78,79,0],'R25':[76,92,0],'R19':[90,77,0],'R23':[130,66,0],'R30':[145,66,90],'TP4':[149,71,0],'BZ1':[102,96,0],'R6':[113,83,0],'R27':[113,79,0],'D1':[131,79,0],'C19':[143,83,0],'C20':[143,80,0],'C24':[145,102,0],'C22':[119,108,0],'C6':[127,120,0],'L1':[133,113,0],'C21':[129.5,109,0],'F1':[140,107,0],'C5':[127,116.5,0],'C8':[138,118,90],'C7':[138,113,90]})
(root/'positions.json').write_text(json.dumps(positions))
project=json.loads((root/BOARD.with_suffix('.kicad_pro')).read_text());old=json.loads((Path('/tmp/smartdb_review/violations_update')/BOARD.with_suffix('.kicad_pro')).read_text())
project['board']['design_settings']['rules']=old['board']['design_settings']['rules'];project['net_settings']=old['net_settings']
project['net_settings']['netclass_patterns'] += [{'netclass':'Power','pattern':'ADC_3V3'},{'netclass':'Power','pattern':'BUCK_SW'}]
(root/BOARD.with_suffix('.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
