"""Prepare a local autorouter job while retaining both inner ground planes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import parse,first,children,put,save
p=ROOT/'work/remaining.dsn'
p.write_text((ROOT/'work/remaining_source.dsn').read_text().replace('    (string_quote ")\n',''))
b=parse(p)
for layer in children(first(b,'structure'),'layer'):
    if layer[1] in ['In1.Cu','In2.Cu']:put(layer,'type','power')
save(p,b)
p.write_text(p.read_text().replace('(parser','(parser\n    (string_quote ")',1))
print('Prepared all remaining nets; existing routes fixed; inner planes preserved.')
