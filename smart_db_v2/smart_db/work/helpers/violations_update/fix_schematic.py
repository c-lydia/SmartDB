import sys, shutil, copy, json, hashlib
from pathlib import Path
sys.path.insert(0, '/tmp/smartdb_review/module_update')
from cad_edit import *

OUT = Path('/tmp/smartdb_review/violations_update')
dest = OUT / BOARD.parent
dest.mkdir(parents=True, exist_ok=True)
for suffix in ('.kicad_sch', '.kicad_pcb', '.kicad_pro'):
    if not (OUT / BOARD.with_suffix(suffix)).exists():
        shutil.copy2(SOURCE / BOARD.with_suffix(suffix), OUT / BOARD.with_suffix(suffix))
sch = parse(SOURCE / BOARD.with_suffix('.kicad_sch'))
originals = {props(s)['Reference']: s for s in children(sch, 'symbol')}
lib = first(sch, 'lib_symbols')
defs = {s[1]: s for s in children(lib, 'symbol')}

def library_symbol(libid):
    if libid in defs: return defs[libid]
    ln, name = libid.split(':')
    collection = {s[1]:s for s in children(parse(SYMBOLS / (ln+'.kicad_sym')), 'symbol')}
    symbol = copy.deepcopy(collection[name])
    if first(symbol, 'extends'):
        parent = copy.deepcopy(collection[value(symbol,'extends')])
        symbol.remove(first(symbol,'extends'))
        symbol += [n for n in parent[2:] if isinstance(n,list) and n[0]!='property']
        for n in children(symbol,'symbol'): n[1] = Quoted(n[1].replace(parent[1], name))
    symbol[1] = Quoted(libid)
    lib.append(symbol); defs[libid] = symbol
    return symbol

# Project-local symbol: exact LDL1117 pinout, not an adjustable regulator alias.
reg = copy.deepcopy(library_symbol('Regulator_Linear:AP1117-15'))
reg[1] = Quoted('SmartDB:LDL1117S33R')
for n in children(reg,'symbol'): n[1] = Quoted(n[1].replace('AP1117-15','LDL1117S33R'))
prop(reg,'Value','LDL1117S33R')
prop(reg,'Datasheet','https://www.st.com/resource/en/datasheet/ldl1117.pdf')
prop(reg,'Description','Fixed 3.3V, 1.2A LDO; ceramic output capacitor; verify thermal budget')
lib.append(reg); defs[reg[1]] = reg
localreg = copy.deepcopy(reg); localreg[1] = Quoted('LDL1117S33R')
save(dest/'SmartDB.kicad_sym',['kicad_symbol_lib',['version','20241209'],['generator',Quoted('kicad_symbol_editor')],localreg])
(dest/'sym-lib-table').write_text('(sym_lib_table\n  (version 7)\n  (lib (name "SmartDB")(type "KiCad")(uri "${KIPRJMOD}/SmartDB.kicad_sym")(options "")(descr "SmartDB project symbols"))\n)\n')

def old_region(x,y):
    x,y = float(x),float(y)
    return (x<139 and 10<=y<=140) or (x<177 and 140<=y<=203)

for item in list(sch):
    if not isinstance(item,list): continue
    if item[0] in ('symbol','junction','global_label','label','no_connect','text'):
        at=first(item,'at')
        if at and old_region(*at[1:3]): sch.remove(item)
    elif item[0]=='wire':
        pts=first(item,'pts')[1:]
        if any(old_region(*p[1:3]) for p in pts):
            assert all(old_region(*p[1:3]) for p in pts), item
            sch.remove(item)
    elif item[0]=='rectangle' and old_region(*first(item,'start')[1:]): sch.remove(item)

def place(ref, x,y,angle,name,mapping,libid=None,footprint=None,template=None):
    s=copy.deepcopy(originals.get(ref,originals[template or 'C9']))
    if ref not in originals: put(s,'uuid',uid())
    if libid:
        put(s,'lib_id',Quoted(libid))
        s[:]=[p for p in s if not (isinstance(p,list) and p[0]=='property' and p[1] not in ('Reference','Value','Footprint','Datasheet','Description'))]
    definition=library_symbol(value(s,'lib_id'))
    prop(s,'Reference',ref); prop(s,'Value',name)
    if libid:
        for key in ('Footprint','Datasheet','Description'): prop(s,key,props(definition).get(key,''))
    if footprint: prop(s,'Footprint',footprint)
    put(s,'at',num(x),num(y),num(angle))
    s[:]=[p for p in s if not(isinstance(p,list) and p[0] in ('pin','mirror'))]
    for p in pins(definition): s.append(['pin',Quoted(value(p,'number')),['uuid',uid()]])
    for p in children(s,'property'):
        put(p,'at',num(x+3.81),num(y-2.54 if p[1]=='Reference' else y),num(angle%180))
        put(p,'effects',['font',['size','1','1']],['justify','left'])
        if p[1] not in ('Reference','Value'): put(p,'hide','yes')
    if ref in ('U5','D7','J4','U3','U1','K1'):
        top={'U5':33.02,'D7':10.16,'J4':30.48,'U3':12.7,'U1':17.78,'K1':15.24}[ref]
        for p in children(s,'property'):
            if p[1] in ('Reference','Value'): put(p,'at',num(x-5.08),num(y-top+(2.54 if p[1]=='Value' else 0)),num(angle%180))
    if ref in ('F1','D6','J2','D8'):
        for p in children(s,'property'):
            if p[1] in ('Reference','Value'): put(p,'at',num(x-5.08),num(y-12.7+(2.54 if p[1]=='Value' else 0)),num(angle%180))
    for project in children(first(s,'instances'),'project'):
        for path in children(project,'path'): put(path,'reference',Quoted(ref))
    sch.append(s); connect(sch,s,definition,mapping)
    return s

# Bench relay: 5V coil, normally-open dry contacts, separate low-voltage load connector.
# No relay contact shares a CT or logic net. This is not a mains switching design.
place('K1',99.06,83.82,0,'G5LE-1 DC5',{'1':'LOAD_IN','2':'RELAY_LOW','3':'LOAD_OUT','5':'LOGIC_5V_FUSED'},'Relay:G5LE-1')
place('Q1',60.96,88.9,0,'AO3400A',{'1':'RELAY_GATE','2':'BGND','3':'RELAY_LOW'},'Transistor_FET:AO3400A')
place('R6',25.4,76.2,90,'100',{'1':'CTL','2':'RELAY_GATE'})
place('R28',25.4,93.98,0,'100k',{'1':'RELAY_GATE','2':'BGND'},template='R27')
place('D1',60.96,69.85,90,'1N4007',{'1':'LOGIC_5V_FUSED','2':'RELAY_LOW'})
place('J5',127,86.36,0,'LOAD: 5-24VDC / 1A MAX',{'1':'LOAD_IN','2':'LOAD_OUT'},'Connector:Screw_Terminal_01x02',footprint=props(originals['J2'])['Footprint'],template='J2')
place('C19',386.08,116.84,0,'10uF 10V X7R',{'1':'LOGIC_5V_FUSED','2':'BGND'},template='C9')
place('C20',386.08,142.24,0,'100nF 10V X7R',{'1':'LOGIC_5V_FUSED','2':'BGND'},template='C9')

# CT differential input, deliberately separate from the relay/load circuit.
put(sch,'paper',Quoted('A2'))
place('J1',411.48,30.48,0,'SCT-013-000 ONLY',{'T':'CT_HI','S':'CT_BIAS'})
place('R23',449.58,30.48,0,'18 ohm 1% 0.25W',{'1':'CT_HI','2':'CT_BIAS'})
place('U1',508,43.18,0,'ADS1115IDGS',{'1':'BGND','3':'BGND','4':'ADC_AIN0','5':'ADC_AIN1','6':'BGND','7':'BGND','8':'VCC','9':'SDA','10':'SCL'})
for ref,x,y,name,mapping in [
    ('R3',411.48,71.12,'10k 1%',{'1':'VCC','2':'CT_BIAS'}),
    ('R4',447.04,71.12,'10k 1%',{'1':'CT_BIAS','2':'BGND'}),
    ('C2',482.6,83.82,'10uF',{'1':'CT_BIAS','2':'BGND'}),
    ('R1',411.48,116.84,'1k 1%',{'1':'CT_HI','2':'ADC_AIN0'}),
    ('R2',447.04,116.84,'1k 1%',{'1':'CT_BIAS','2':'ADC_AIN1'}),
    ('C1',482.6,121.92,'220nF',{'1':'ADC_AIN0','2':'ADC_AIN1'}),
    ('C3',411.48,160.02,'100nF',{'1':'VCC','2':'BGND'}),
    ('C4',447.04,160.02,'1uF',{'1':'VCC','2':'BGND'}),
    ('R9',485.14,160.02,'1k',{'1':'VCC','2':'ADC_LED_A'}),
    ('D2',523.24,160.02,'ADC POWER',{'1':'BGND','2':'ADC_LED_A'})]:
    place(ref,x,y,90 if ref=='D2' else 0,name,mapping)
place('D9',538.48,86.36,0,'BAT54S',{'1':'BGND','2':'VCC','3':'ADC_AIN0'},'Diode:BAT54S',template='D7')
place('D10',538.48,121.92,0,'BAT54S',{'1':'BGND','2':'VCC','3':'ADC_AIN1'},'Diode:BAT54S',template='D7')
for x,y,txt in [(406.4,10.16,'AC CURRENT INPUT - CT only, never connect a voltage source to J1'),
    (406.4,190.5,'SCT-013-000: 100A : 50mA assumed from project sensor choice; verify actual sensor.'),
    (406.4,198.12,'18-ohm burden: 0.9Vrms / 1.27Vpk at nominal 100A; CT_BIAS = VCC/2.'),
    (406.4,205.74,'ADC: differential AIN0-AIN1, +/-2.048V PGA, 860SPS. 220nF differential filter.'),
    (406.4,213.36,'Calibrate 50/60Hz RMS and validate clamp behavior; this CT cannot measure DC.'),
    (15.24,55.88,'BENCH RELAY ONLY: 5-24VDC, <=1A resistive load. No mains.'),
    (15.24,48.26,'J5: contact loop only; external current-limited supply and load wired in series.')]:
    sch.append(['text',Quoted(txt),['at',num(x),num(y),'0'],['effects',['font',['size','1','1']],['justify','left']],['uuid',uid()]])

# External regulated 5V is the documented logic input. SW1 was a momentary power switch.
# Remove it; power is disconnected at J2. F1/F2 ratings remain explicit review items.
place('J2',25.4,116.84,180,'5V INPUT (1=GND, 2=+5V)',{'1':'BGND','2':'LOGIC_5V_IN'})
place('F1',63.5,114.3,90,'PTC (rating TBD)',{'1':'LOGIC_5V_IN','2':'LOGIC_5V_FUSED'})
place('U3',104.14,119.38,0,'LDL1117S33R',{'1':'BGND','2':'VCC','3':'LOGIC_5V_FUSED'},'SmartDB:LDL1117S33R')
for ref,x,y,name,net in [('C5',25.4,144.78,'4.7uF 10V X7R','LOGIC_5V_FUSED'),('C6',68.58,144.78,'100nF 10V X7R','LOGIC_5V_FUSED'),('C7',25.4,175.26,'10uF 10V X7R','VCC'),('C8',68.58,175.26,'100nF 10V X7R','VCC')]:
    place(ref,x,y,0,name,{'1':net,'2':'BGND'})

# Self-powered CP2102N, internal regulator bypassed per Figure 2.3.
place('U5',177.8,241.3,0,'CP2102N-A02-GQFN28',{'3':'BGND','29':'BGND','4':'USB_D+','5':'USB_D-','6':'VCC','7':'VCC','8':'USB_VBUS_SENSE','9':'USB_RESET','25':'RX','26':'TX'})
for ref,x,y,name in [('C15',25.4,218.44,'100nF'),('C16',63.5,218.44,'4.7uF'),('C17',101.6,218.44,'4.7uF'),('C18',139.7,218.44,'100nF')]:
    place(ref,x,y,0,name,{'1':'VCC','2':'BGND'})
place('R21',40.64,243.84,0,'1k',{'1':'VCC','2':'USB_RESET'})
place('R19',78.74,243.84,0,'22.1k',{'1':'USB_VBUS','2':'USB_VBUS_SENSE'})
place('R20',116.84,243.84,0,'47.5k',{'1':'USB_VBUS_SENSE','2':'BGND'})
place('R22',25.4,271.78,90,'330',{'1':'VCC','2':'USB_LED_A'})
place('D8',63.5,271.78,90,'USB BRIDGE POWER',{'1':'BGND','2':'USB_LED_A'})
place('D7',243.84,231.14,0,'SP0503BAHTG',{'1':'BGND','2':'USB_D+','3':'USB_D-','4':'USB_VBUS'},'Power_Protection:SP0503BAHT')
place('R24',243.84,259.08,0,'5.1k',{'1':'USB_CC1','2':'BGND'})
place('R25',279.4,259.08,0,'5.1k',{'1':'USB_CC2','2':'BGND'})
usbmap={p:'BGND' for p in ('A1','A12','B1','B12','SH')}
usbmap.update({p:'USB_VBUS' for p in ('A4','A9','B4','B9')})
usbmap.update({'A5':'USB_CC1','B5':'USB_CC2','A6':'USB_D+','B6':'USB_D+','A7':'USB_D-','B7':'USB_D-'})
place('J4',340.36,218.44,0,'USB_C_Receptacle_USB2.0_14P',usbmap)

# Exact six-terminal RGB device: all cathodes are now represented and grounded.
old=originals['D6']; definition=defs[value(old,'lib_id')]
points=[pin_position(old,p)[:2] for p in pins(definition)]
for p in list(sch):
    if not isinstance(p,list): continue
    if p is old: sch.remove(p)
    elif p[0]=='wire' and any(any(abs(float(q[1])-x)<.001 and abs(float(q[2])-y)<.001 for x,y in points) for q in first(p,'pts')[1:]):
        ends=[tuple(map(float,q[1:])) for q in first(p,'pts')[1:]]
        sch.remove(p)
        for lab in list(children(sch,'global_label')):
            if tuple(map(float,first(lab,'at')[1:3])) in ends: sch.remove(lab)
place('D6',248.92,160.02,0,'SMLVN6RGB1U1',{'1':'LED_B_A','2':'LED_R_A','3':'LED_G_A','4':'BGND','5':'BGND','6':'BGND'},'LED:SMLVN6RGB')

for s in children(sch,'symbol'):
    if props(s)['Reference'] in ('SW2','SW3'):
        prop(s,'Footprint','Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2')
        prop(s,'Description','KMR221NG LFS, non-grounded momentary switch')
        prop(s,'Datasheet','https://www.ckswitches.com/media/1479/kmr2.pdf')
for l in children(sch,'global_label'):
    if l[1]=='GND': l[1]=Quoted('BGND')

# Flags only on real external/fused power domains; no electrical-error exclusions.
library_symbol('power:PWR_FLAG')
for i,(net,x,y) in enumerate([('BGND',104.14,152.4),('LOGIC_5V_FUSED',104.14,172.72),('MCU_3V3',365.76,190.5)],1):
    flag=place('#FLG0'+str(i),x,y,0,'PWR_FLAG',{'1':net},'power:PWR_FLAG',template='C9')
    put(flag,'in_bom','no'); put(flag,'on_board','no')

for t in children(sch,'text'):
    if 'MCU MODULE REVISION' in t[1]: t[1]=Quoted('LOW-VOLTAGE BENCH REVISION - 5V logic, 5-24VDC / 1A resistive test load only')
    if 'D6 footprint mismatch' in t[1]: t[1]=Quoted('Unrouted draft: relay/CT redesign, fuse/buzzer selection and thermal review still required')
for x,y,txt in [(15.24,101.6,'REGULATED 5V LOGIC INPUT - no raw battery / 12V input'),(15.24,200.66,'USB: self-powered 3.3V; VBUS sense only; UART without hardware flow control'),(15.24,192.0,'Output capacitor must retain >=4.7uF under DC bias. LDO dissipation = (5-3.3)*I.')]:
    sch.append(['text',Quoted(txt),['at',num(x),num(y),'0'],['effects',['font',['size','1.0','1.0']],['justify','left']],['uuid',uid()]])
title=first(sch,'title_block'); put(title,'title',Quoted('SmartDB v2 - logic circuit corrections / routing draft')); put(title,'rev',Quoted('2-logic-draft'))
put(title,'comment','1',Quoted('Low-voltage bench draft; CT and thermal validation pending; no mains'))
save(OUT/BOARD.with_suffix('.kicad_sch'),sch)
print('Staged schematic',len(children(sch,'symbol')),'symbols')
