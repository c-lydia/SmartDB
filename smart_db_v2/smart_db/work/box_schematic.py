import sys,math,xml.etree.ElementTree as ET
sys.path.insert(0,'/tmp/smartdb_review/module_update')
from cad_edit import *
root=Path('/tmp/smartdb_review/compact');p=root/BOARD.with_suffix('.kicad_sch');s=parse(p)
syms={props(x)['Reference']:x for x in children(s,'symbol')};defs={x[1]:x for x in children(first(s,'lib_symbols'),'symbol')}
maps={r:{} for r in syms}
for net in ET.parse(root/'netlist.xml').findall('./nets/net'):
 for n in net.findall('node'):
  if n.get('ref') in maps:maps[n.get('ref')][n.get('pin')]=net.get('name') if not net.get('name').startswith('unconnected-') else None
for ref,x in syms.items():
 if not ref.startswith('#'):continue
 for pin in pins(defs[value(x,'lib_id')]):
  a,b,d=pin_position(x,pin);r=math.radians(d);xy=(round(a-2.54*math.cos(r),4),round(b+2.54*math.sin(r),4))
  label=next(n for n in children(s,'global_label') if tuple(round(float(v),4) for v in first(n,'at')[1:3])==xy)
  maps[ref][value(pin,'number')]=str(label[1])
s[:]=[n for n in s if not isinstance(n,list) or n[0] not in ['wire','junction','global_label','label','no_connect','text','rectangle','polyline']]
put(s,'paper',Quoted('A1'))
def text(t,x,y,size=2):s.append(['text',Quoted(t),['at',num(x),num(y),'0'],['effects',['font',['size',num(size),num(size)]],['justify','left']],['uuid',uid()]])
def box(title,subtitle,x,y,w=263,h=258):
 s.append(['rectangle',['start',num(x),num(y)],['end',num(x+w),num(y+h)],['stroke',['width','.6'],['type','default']],['fill',['type','none']],['uuid',uid()]])
 text(title,x+5,y+8,3);text(subtitle,x+5,y+17,1.6)
placed=set()
def place(ref,x,y,angle=0):
 x=round(x/1.27)*1.27;y=round(y/1.27)*1.27
 o=syms[ref];put(o,'at',num(x),num(y),num(angle));o[:]=[n for n in o if not isinstance(n,list) or n[0]!='mirror']
 definition=defs[value(o,'lib_id')]
 # Put identity above the symbol's pin envelope, with values on a second line.
 ps=[pin_position(o,p) for p in pins(definition)];top=min([v[1] for v in ps]+[y-3])-5
 for a in children(o,'property'):
  if a[1] in ['Reference','Value']:
   put(a,'at',num(x-4),num(top+(2.6 if a[1]=='Value' else 0)),'0');put(a,'effects',['font',['size','1.2','1.2']],['justify','left'])
 connect(s,o,definition,maps[ref]);placed.add(ref)
box('01  POWER / 5 V TO 3.3 V','J2 regulated 5 V only. Buck + local reservoirs. Not battery charging.',12,12)
for ref,x,y,a in [('J2',40,60,0),('F1',100,60,90),('U3',175,70,0),('L1',225,70,90),('C5',40,125,0),('C6',90,125,0),('C21',145,125,0),('C7',200,125,0),('C8',245,125,0),('C22',40,190,0),('#FLG01',100,190,0),('#FLG02',150,190,0),('#FLG03',200,190,0),('#FLG05',245,240,0)]:place(ref,x,y,a)
box('02  USB / UART PROGRAMMING','USB is data only; J2 powers the board. Hold BOOT, pulse RESET.',289,12)
for ref,x,y,a in [('J4',335,90,0),('U5',460,115,0),('D7',390,185,0),('R24',320,185,0),('R25',350,235,0),('R19',395,65,0),('R20',395,115,0),('R21',515,75,0),('C15',435,220,0),('C16',475,220,0),('C17',515,220,0),('C18',515,155,0)]:place(ref,x,y,a)
box('03  ESP32-S3 / BOOT / RESET','ESP32-S3-WROOM-1-N16R8. Module RF keepout on every copper layer.',566,12)
for ref,x,y,a in [('U4',745,130,0),('R29',620,55,90),('C9',600,100,0),('C10',645,100,0),('C23',600,155,0),('R13',650,155,0),('C11',600,225,0),('SW3',650,225,0),('R14',735,225,0),('SW2',790,225,0)]:place(ref,x,y,a)
box('04  CT / ADC ANALOG FRONT END','AC current transformer only. Differential AIN0-AIN1, address 0x48.',12,285,h=280)
for ref,x,y,a in [('J1',40,340,0),('R23',95,340,0),('U1',180,375,0),('R1',40,405,90),('R2',95,405,90),('C1',145,445,0),('D9',220,445,0),('D10',220,510,0),('R3',40,470,0),('R4',90,470,0),('C2',40,530,0),('R30',100,530,90),('C3',155,530,0),('C4',185,530,0),('#FLG04',245,340,0)]:place(ref,x,y,a)
box('05  RELAY / TEST LOAD','Normally-open dry contact loop. 5-24 V DC / 1 A resistive bench target.',289,285,h=280)
for ref,x,y,a in [('K1',465,370,0),('J5',520,445,0),('Q1',390,410,0),('R6',330,405,90),('R28',390,475,0),('R27',330,475,0),('D1',440,475,0),('C19',490,510,0),('C20',530,510,0),('C24',465,540,0)]:place(ref,x,y,a)
box('06  INDICATORS / EXTERNAL I2C','3.3 V logic only. Buzzer part selection and bench measurements pending.',566,285,h=230)
for ref,x,y,a in [('J3',600,335,0),('R7',650,335,0),('R8',700,335,0),('D6',785,345,0),('R16',740,395,90),('R17',740,440,90),('R18',740,485,90),('BZ1',630,395,0),('Q2',630,455,0),('R15',580,435,90),('R26',580,485,0),('D5',680,480,0),('R12',680,425,0),('D2',805,460,0),('R9',805,415,0),('D8',600,500,0),('R22',680,380,90)]:place(ref,x,y,a)
text('MECHANICAL + MEASUREMENT POINTS',570,532,2)
for i,ref in enumerate(['H1','H2','H3','H4','TP1','TP2','TP3','TP4','TP5']):place(ref,578+i*26,551,0)
assert placed==set(syms),(set(syms)-placed,placed-set(syms))
put(first(s,'title_block'),'comment','1',Quoted('COMPACT BENCH PROTOTYPE - NO MAINS - hardware validation required'))
save(p,s)
print('Six boxed subsystems; preserved',len(syms),'symbols and their net assignments.')
