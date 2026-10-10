"""Install project-local models; assert all non-model PCB data is preserved."""
import copy
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import parse,save,children,first,props,prop,Quoted

backup=ROOT/'work/before_step_model_fix'
backup.mkdir(exist_ok=True)
for name in ['smart_db.kicad_pcb','smart_db.kicad_sch','smart_db.kicad_pro','smart_db.step']:
    target=backup/name
    if not target.exists() and (ROOT/name).exists(): shutil.copy2(ROOT/name,target)
board=parse(ROOT/'smart_db.kicad_pcb')
before=copy.deepcopy(board)
sch=parse(ROOT/'smart_db.kicad_sch')
base=next(Path('/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Footprints').glob('x86_64/stable/*/files/footprints'))
models={
 'D6':('LED_SMD','LED_ROHM_SMLVN6','LED_ROHM_SMLVN6_Preview','LED_ROHM_SMLVN6_preview.step'),
 'J1':('Connector_Audio','Jack_3.5mm_CUI_SJ-3523-SMT_Horizontal','Jack_3.5mm_SJ-3523-SMT_Local','SJ-3523-SMT_aligned.step'),
 'J4':('SmartDB','USB_C_Receptacle_Amphenol_12401948E412A_Preview','USB_C_Receptacle_Amphenol_12401948E412A_Preview','USB_C_12401948_preview.step'),
}
for ref,(library,old,new,model) in models.items():
    assert (ROOT/'SmartDB.3dshapes'/model).exists()
    path=ROOT/'SmartDB.pretty'/f'{old}.kicad_mod' if library=='SmartDB' else base/f'{library}.pretty'/f'{old}.kicad_mod'
    lib=parse(path);lib[1]=Quoted(new)
    footprint=next(f for f in children(board,'footprint') if props(f)['Reference']==ref)
    footprint[1]=Quoted('SmartDB:'+new)
    for node in [lib,footprint]:first(node,'model')[1]=Quoted('${KIPRJMOD}/SmartDB.3dshapes/'+model)
    save(ROOT/'SmartDB.pretty'/f'{new}.kicad_mod',lib)
    symbol=next(s for s in children(sch,'symbol') if props(s)['Reference']==ref)
    prop(symbol,'Footprint','SmartDB:'+new)
def strip_models(b):
    b=copy.deepcopy(b)
    for f in children(b,'footprint'):
        if props(f)['Reference'] in models:
            f[1]='MODEL_ONLY_CHANGE'
            f[:]=[v for v in f if not(isinstance(v,list) and v and v[0]=='model')]
    return b
assert strip_models(board)==strip_models(before),'Non-model board data changed'
save(ROOT/'smart_db.kicad_pcb',board)
save(ROOT/'smart_db.kicad_sch',sch)
print('Installed 3 local STEP models; all non-model board data identical.')
