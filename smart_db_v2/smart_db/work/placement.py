import sys,json,xml.etree.ElementTree as ET
sys.path.insert(0,'/tmp/smartdb_review/module_update')
from cad_edit import *
from pcb_edit import load_footprint,refresh_uuids
out=Path('/tmp/smartdb_review/compact');b=parse(out/BOARD.with_suffix('.kicad_pcb'));sch=parse(out/BOARD.with_suffix('.kicad_sch'))
b[:]=[n for n in b if not isinstance(n,list) or n[0] not in ['footprint','segment','via','zone','gr_line','gr_text','gr_poly','gr_circle']]
netmap={}
for net in ET.parse(out/'netlist.xml').findall('./nets/net'):
 for n in net.findall('node'):netmap[n.get('ref'),n.get('pin')]=(net.get('name').replace('/','{slash}'),n.get('pinfunction'),n.get('pintype'))
# All coordinates are mm; through-hole connector mating faces point outwards.
pos={
'U4':(87,54,0),'C9':(74,50,0),'C10':(74,53,0),'C23':(74,57,0),'R29':(74,61,0),'R13':(74,64,0),'C11':(74,67,0),
'J3':(68,72,180),'R7':(100,55,0),'R8':(100,58,0),'SW2':(104,65,0),'R14':(100,62,0),'SW3':(104,72,0),
'D6':(86,73,0),'R16':(80,70,0),'R17':(80,73,0),'R18':(80,76,0),'Q2':(98,81,0),'R15':(94,79,0),'R26':(94,83,0),'BZ1':(102,86,0),
'J4':(69,83,-90),'U5':(83,83,0),'D7':(77.5,86,0),'R24':(76,79,0),'R25':(76,88.5,0),'R19':(81,77,0),'R20':(86,77,0),'R21':(86,88,0),
'C15':(78,91,0),'C16':(78,94,0),'C17':(82.5,94,0),'C18':(83,91,0),
'J1':(138,56,0),'R23':(135,65,0),'U1':(132,74,0),'R1':(126,70,0),'R2':(126,74,0),'C1':(128,78,90),'D9':(121,69,0),'D10':(121,74,0),
'R3':(138,73,0),'R4':(138,76,0),'C2':(138,80,0),'C3':(136,70,0),'C4':(141,70,0),'R30':(141,66,90),'R9':(146,72,90),'D2':(146,76,0),
'K1':(131,84,0),'J5':(149,94,90),'Q1':(117,86,0),'R6':(112,86,0),'R28':(117,90,0),'R27':(112,90,0),'D1':(119,99,90),'C19':(139,83,0),'C20':(139,86,0),'C24':(145,103,0),
'J2':(149,114,90),'F1':(140,111,0),'U3':(127,113,0),'L1':(133,113,90),'C21':(130,109,90),'C5':(127,118,0),'C6':(124,115.5,90),'C7':(138,113,90),'C8':(138,118,90),'C22':(143,118,0),
'D5':(114,115,0),'R12':(114,111,90),'D8':(94,95,0),'R22':(94,91,90),
'H1':(64,51,0),'H2':(151,51,0),'H3':(64,121,0),'H4':(151,121,0),
'TP1':(136,108,0),'TP2':(119,117,0),'TP3':(71,61,0),'TP4':(145,69,0),'TP5':(119,121,0)}
syms={props(s)['Reference']:s for s in children(sch,'symbol') if not props(s)['Reference'].startswith('#')}
assert set(pos)==set(syms),(set(syms)-set(pos),set(pos)-set(syms))
for ref,s in syms.items():
 f=load_footprint(props(s)['Footprint']);refresh_uuids(f);put(f,'uuid',uid());put(f,'at','0','0','0');put(f,'path',Quoted('/'+value(s,'uuid')));put(f,'sheetname',Quoted('/'));put(f,'sheetfile',Quoted('smart_db.kicad_sch'))
 for key in ['Reference','Value','Datasheet','Description']:
  q=prop(f,key,props(s).get(key,''))
  if key!='Reference':put(q,'hide','yes')
  if key not in ['Reference','Value']:
   put(q,'at','0','0','0');put(q,'layer',Quoted('F.Fab'));put(q,'effects',['font',['size','1','1'],['thickness','.15']]);put(q,'uuid',uid())
 # Small component IDs are on fab/assembly; functional connector labels go on silk.
 if ref[0] in ['R','C','D','Q','L','F'] or ref.startswith('TP'):put(prop(f,'Reference',ref),'hide','yes')
 for pad in children(f,'pad'):
  data=netmap.get((ref,str(pad[1])))
  if data:
   net,fn,kind=data;put(pad,'net',Quoted(net))
   if fn:put(pad,'pinfunction',Quoted(fn))
   if kind:put(pad,'pintype',Quoted(kind))
 b.append(f)
put(first(b,'title_block'),'rev',Quoted('2-compact')) if first(b,'title_block') else None
save(out/BOARD.with_suffix('.kicad_pcb'),b);(out/'positions.json').write_text(json.dumps(pos))
# Plane layers stay free of signal tracks. In2 is continuous GND too; power is routed as wide outer copper.
pr=out/BOARD.with_suffix('.kicad_pro');project=json.loads(pr.read_text())
for c in project['net_settings']['classes']:
 if c['name']=='Power':c['track_width']=.5
project['net_settings']['netclass_patterns'] += [{'netclass':'Power','pattern':'ADC_3V3'},{'netclass':'Power','pattern':'BUCK_SW'},{'netclass':'Default','pattern':'BUCK_BST'}]
pr.write_text(json.dumps(project,indent=2)+'\n')
print('Prepared',len(pos),'components for a 95 x 78 mm board.')
