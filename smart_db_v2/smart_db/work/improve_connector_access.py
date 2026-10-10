"""Move the I2C header and mid-mount USB to the left board edge before routing."""
from pathlib import Path
import copy
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'work/helpers/module_update'))
from cad_edit import *

path = ROOT / 'smart_db.kicad_pcb'
b = parse(path)
assert not children(b, 'segment') and not children(b, 'via'), 'Do not replay after routing'
f = next(f for f in children(b, 'footprint') if props(f)['Reference'] == 'J3')
libpath = next(Path('/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Footprints').glob('x86_64/stable/*/files/footprints/Connector_PinHeader_2.54mm.pretty/PinHeader_1x04_P2.54mm_Horizontal.kicad_mod'))
lib = parse(libpath)
lib[1] = Quoted('PinHeader_1x04_P2.54mm_Horizontal_Edge')
# The protruding metal pins remain visible in the fab layer and 3D model.
# Their decorative silk cannot be printed outside the board.
for node in [lib, f]:
    for g in children(node, 'fp_line') + children(node, 'fp_rect'):
        if value(g, 'layer') == 'F.SilkS':
            if max(float(first(g, k)[1]) for k in ['start', 'end']) > 4.4:
                put(g, 'layer', Quoted('F.Fab'))
save(ROOT / 'SmartDB.pretty/PinHeader_1x04_P2.54mm_Horizontal_Edge.kicad_mod', lib)
f[1] = Quoted('SmartDB:PinHeader_1x04_P2.54mm_Horizontal_Edge')
put(prop(f, 'Reference', 'J3'), 'at', '-1', '-2.5', '0')
sch = parse(ROOT / 'smart_db.kicad_sch')
s = next(s for s in children(sch, 'symbol') if props(s)['Reference'] == 'J3')
prop(s, 'Footprint', str(f[1]))
save(ROOT / 'smart_db.kicad_sch', sch)
# Remove the deep recess connecting the original mid-mount cutout to the edge.
# The connector's own Edge.Cuts geometry is retained unchanged.
for n in list(children(b, 'gr_line')):
    if value(n, 'layer') != 'Edge.Cuts': continue
    a,c = first(n, 'start'),first(n, 'end')
    if a[2] == c[2] and a[2] in ['76.3', '89.7']:
        b.remove(n)
save(path, b)
print('Prepared project-local edge header and USB outline.')
