"""Constrain the local routing job to the connectors and their supply networks."""
from pathlib import Path
import sys
import copy
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'work/helpers/module_update'))
from cad_edit import *
p = ROOT / 'work/connectors.dsn'
original = (ROOT / 'work/connectors_source.dsn').read_text()
# The Specctra quote declaration isn't a normal quoted S-expression atom.
p.write_text(original.replace('    (string_quote ")\n', ''))
b = parse(p)
network = first(b, 'network')
selected = {'SDA', 'SCL', 'RX', 'TX', 'BGND', 'VCC', 'MCU_3V3', 'USB_LED_A',
            'USB_CC1', 'USB_CC2', 'USB_D+', 'USB_D-', 'USB_VBUS', 'USB_VBUS_SENSE', 'USB_RESET'}
skipped = [n[1] for n in children(network, 'net') if n[1] not in selected]
for c in list(children(network, 'class')):
    deferred = copy.deepcopy(c)
    deferred[1] = 'Deferred_' + str(c[1])
    deferred[:] = [deferred[0], deferred[1], *[n for n in deferred[2:] if isinstance(n, list) or n not in selected]]
    if any(not isinstance(n, list) for n in deferred[2:]): network.append(deferred)
    c[:] = [c[0], c[1], *[n for n in c[2:] if isinstance(n, list) or n in selected]]
    if not any(not isinstance(n, list) for n in c[2:]): network.remove(c)
structure = first(b, 'structure')
settings = ['autoroute_settings', ['fanout', 'off'], ['autoroute', 'on'], ['postroute', 'on']]
for layer in children(structure, 'layer'):
    inner = layer[1] in ['In1.Cu', 'In2.Cu']
    if inner: put(layer, 'type', 'power')
    settings.append(['layer_rule', layer[1], ['active', 'off' if inner else 'on'],
                     ['preferred_direction', 'horizontal' if layer[1] == 'F.Cu' else 'vertical']])
# Power-type inner layers remain unroutable; outer layers are signal layers.
save(p, b)
p.write_text(p.read_text().replace('(parser', '(parser\n    (string_quote ")', 1))
print('Selected nets:', ', '.join(sorted(selected)))
