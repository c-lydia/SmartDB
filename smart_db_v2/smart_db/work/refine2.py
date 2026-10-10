import sys,json,copy
sys.path.insert(0,'/tmp/smartdb_review/module_update')
from cad_edit import *
from pcb_edit import load_footprint,refresh_uuids
root=Path('/tmp/smartdb_review/compact');p=root/BOARD.with_suffix('.kicad_pcb');b=parse(p);sp=root/BOARD.with_suffix('.kicad_sch');sch=parse(sp);syms={props(s)['Reference']:s for s in children(sch,'symbol')}
def replace(ref,libid):
 old=next(f for f in children(b,'footprint') if props(f)['Reference']==ref);new=load_footprint(libid);refresh_uuids(new)
 for key in ['uuid','path','sheetname','sheetfile']:put(new,key,*first(old,key)[1:])
 put(new,'at','0','0','0')
 new[:]=[n for n in new if not isinstance(n,list) or n[0]!='property'];new += copy.deepcopy(children(old,'property'))
 for pad in children(new,'pad'):
  op=next(q for q in children(old,'pad') if q[1]==pad[1])
  for key in ['net','pinfunction','pintype']:
   a=first(op,key)
   if a:put(pad,key,*a[1:])
 b[b.index(old)]=new;prop(syms[ref],'Footprint',libid)
for ref in ['C15','C18']:replace(ref,'Capacitor_SMD:C_0603_1608Metric')
# Explicit edge-overhang variant: only off-board silkscreen is clipped.
mod=load_footprint('RF_Module:ESP32-S3-WROOM-1');mod[1]=Quoted('ESP32_S3_WROOM_1_Edge')
for n in mod:
 if not isinstance(n,list) or n[0]!='fp_line' or value(n,'layer')!='F.SilkS':continue
 a,c=first(n,'start'),first(n,'end')
 if float(a[2])<-6.7 and float(c[2])<-6.7:put(n,'layer',Quoted('F.Fab'))
 elif float(a[2])<-6.7:a[2]='-6.7'
 elif float(c[2])<-6.7:c[2]='-6.7'
dir_=root/BOARD.parent/'SmartDB.pretty';dir_.mkdir(exist_ok=True);save(dir_/'ESP32_S3_WROOM_1_Edge.kicad_mod',mod)
(root/BOARD.parent/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "SmartDB") (type "KiCad") (uri "${KIPRJMOD}/SmartDB.pretty") (options "") (descr "SmartDB edge-placement variants")))\n')
f=next(f for f in children(b,'footprint') if props(f)['Reference']=='U4');f[1]=Quoted('SmartDB:ESP32_S3_WROOM_1_Edge');prop(syms['U4'],'Footprint','SmartDB:ESP32_S3_WROOM_1_Edge')
# Keep K1's identifier clear of the flyback diode.
f=next(f for f in children(b,'footprint') if props(f)['Reference']=='K1');put(prop(f,'Reference','K1'),'at','0','21.8','0')
save(p,b);save(sp,sch)
pos=json.loads((root/'positions.json').read_text());pos.update({'R13':[74,70,0],'C11':[78,67,90],'R24':[73,76,0],'R25':[73,94,0],'D7':[77.5,81,0],'C15':[78.3,85.2,180],'C18':[78.3,87.7,180],'C16':[78,91,180],'C17':[83,91,180],'C3':[137,73,0],'R3':[141,77,0],'R4':[141,80,0],'C2':[136,80,0],'D1':[132,81,0]})
(root/'positions.json').write_text(json.dumps(pos))
