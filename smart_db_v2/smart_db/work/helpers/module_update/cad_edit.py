import copy
import json
import math
import re
import uuid
from pathlib import Path


class Quoted(str):
    pass


RAW = {}


def parse(path):
    text = Path(path).read_text()
    stack = []
    root = None
    for m in re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text):
        t = m.group()
        if t == '(':
            node = []
            if stack:
                stack[-1][0].append(node)
            else:
                root = node
            stack.append((node, m.start()))
        elif t == ')':
            node, start = stack.pop()
            RAW[id(node)] = (repr(node), text[start:m.end()])
        else:
            stack[-1][0].append(Quoted(json.loads(t)) if t.startswith('"') else t)
    assert not stack
    return root


def atom(value):
    return json.dumps(str(value), ensure_ascii=False) if isinstance(value, Quoted) else str(value)


def dump(node, depth=0):
    raw = RAW.get(id(node))
    if raw is not None and raw[0] == repr(node):
        return raw[1]
    if not any(isinstance(x, list) for x in node):
        return '(' + ' '.join(atom(x) for x in node) + ')'
    out = '(' + atom(node[0])
    for child in node[1:]:
        out += ('\n' + '\t' * (depth + 1) + dump(child, depth + 1)) if isinstance(child, list) else ' ' + atom(child)
    return out + '\n' + '\t' * depth + ')'


def save(path, root):
    Path(path).write_text(dump(root) + '\n')


def children(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def first(node, key):
    return next(iter(children(node, key)), None)


def value(node, key):
    x = first(node, key)
    return x[1] if x else None


def put(node, key, *args):
    x = first(node, key)
    if x is None:
        node.append([key, *args])
    else:
        x[:] = [key, *args]


def props(node):
    return {p[1]: p[2] for p in children(node, 'property')}


def prop(node, key, text):
    p = next((p for p in children(node, 'property') if p[1] == key), None)
    if p is None:
        p = ['property', Quoted(key), Quoted(text)]
        node.append(p)
    else:
        p[2] = Quoted(text)
    return p


def uid():
    return Quoted(str(uuid.uuid4()))


def num(v):
    return str(round(float(v), 5))


def pins(symbol):
    return [p for unit in children(symbol, 'symbol') for p in children(unit, 'pin')]


def pin_position(instance, pin):
    at = first(instance, 'at')
    x, y, angle = map(float, at[1:])
    px, py, pa = map(float, first(pin, 'at')[1:])
    r = math.radians(angle)
    return x + px * math.cos(r) - py * math.sin(r), y - px * math.sin(r) - py * math.cos(r), (pa + angle) % 360


def wire(x, y, xx, yy):
    return ['wire', ['pts', ['xy', num(x), num(y)], ['xy', num(xx), num(yy)]], ['stroke', ['width', '0'], ['type', 'default']], ['uuid', uid()]]


def connect(schematic, instance, definition, mapping):
    seen = set()
    for p in pins(definition):
        number = str(value(p, 'number'))
        x, y, direction = pin_position(instance, p)
        net = mapping.get(number)
        if net == '@wire':
            continue
        key = (round(x, 4), round(y, 4), net)
        if key in seen:
            continue
        seen.add(key)
        if net is None:
            schematic.append(['no_connect', ['at', num(x), num(y)], ['uuid', uid()]])
            continue
        r = math.radians(direction)
        xx, yy = x - 2.54 * math.cos(r), y + 2.54 * math.sin(r)
        schematic.append(wire(x, y, xx, yy))
        angle = (direction + 180) % 360
        schematic.append(['global_label', Quoted(net), ['shape', 'bidirectional'],
                          ['at', num(xx), num(yy), num(angle)],
                          ['effects', ['font', ['size', '1.0', '1.0']], ['justify', 'left' if angle in (0, 90) else 'right']],
                          ['uuid', uid()]])


SOURCE = Path('/home/chheng-lydia/projects/SmartDB')
STAGE = Path('/tmp/smartdb_review/module_update')
BOARD = Path('smart_db_v2/smart_db/smart_db')
SYMBOLS = Path('/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Symbols/x86_64/stable/active/files/symbols')
FOOTPRINTS = Path('/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Footprints/x86_64/stable/active/files/footprints')

MODULE_MAP = {'1': 'BGND', '2': 'MCU_3V3', '3': 'EN', '4': 'CTL', '5': 'BUZZER_DRIVE',
              '6': 'LED_R', '7': 'LED_G', '12': 'LED_B', '18': 'SDA', '27': 'BOOT',
              '36': 'TX', '37': 'RX', '38': 'SCL', '40': 'BGND', '41': 'BGND'}


def make_schematic():
    sch = parse(SOURCE / BOARD.with_suffix('.kicad_sch'))
    originals = {props(s)['Reference']: s for s in children(sch, 'symbol')}
    lib = first(sch, 'lib_symbols')
    defs = {s[1]: s for s in children(lib, 'symbol')}
    module_lib = parse(SYMBOLS / 'RF_Module.kicad_sym')
    module = copy.deepcopy(next(s for s in children(module_lib, 'symbol') if s[1] == 'ESP32-S3-WROOM-1'))
    module[1] = Quoted('RF_Module:ESP32-S3-WROOM-1')
    lib.remove(defs['MCU_Espressif:ESP32-S3'])
    lib.append(module)
    defs[module[1]] = module

    def inside(x, y):
        return 139.7 <= float(x) <= 283.21 and 13.97 <= float(y) <= 138.43

    region_refs = set()
    for s in children(sch, 'symbol'):
        at = first(s, 'at')
        if inside(*at[1:3]):
            region_refs.add(props(s)['Reference'])
            sch.remove(s)
    for item in list(sch):
        if not isinstance(item, list):
            continue
        if item[0] in ('junction', 'global_label', 'label', 'no_connect'):
            at = first(item, 'at')
            if inside(*at[1:3]):
                sch.remove(item)
        elif item[0] == 'wire':
            points = first(item, 'pts')[1:]
            if any(inside(*p[1:3]) for p in points):
                assert all(inside(*p[1:3]) for p in points), 'Unexpected wire across MCU region boundary'
                sch.remove(item)
        elif item[0] == 'rectangle':
            if float(first(item, 'start')[1]) == 139.7:
                sch.remove(item)

    # Expand only the MCU drawing area; the power/relay/ADC/USB sections stay as reviewed.
    put(sch, 'paper', Quoted('A3'))
    sch.append(['title_block', ['title', Quoted('SmartDB v2 - ESP32-S3 module migration (routing draft)')],
                ['date', Quoted('2026-10-08')], ['rev', Quoted('2-module-draft')],
                ['comment', '1', Quoted('Power, relay and ADC circuits still require correction; not for fabrication')]])

    cfg = {
        'U4': (241.3, 88.9, 0, 'ESP32-S3-WROOM-1-N16R8', MODULE_MAP),
        'F2': (165.1, 25.4, 90, 'Fuse (rating TBD)', {'1': 'VCC', '2': 'MCU_3V3'}),
        'C9': (198.12, 38.1, 0, '10uF', {'1': 'MCU_3V3', '2': 'BGND'}),
        'C10': (220.98, 38.1, 0, '100nF', {'1': 'MCU_3V3', '2': 'BGND'}),
        'R13': (165.1, 58.42, 0, '10k', {'1': 'MCU_3V3', '2': 'EN'}),
        'C11': (187.96, 58.42, 0, '1uF', {'1': 'EN', '2': 'BGND'}),
        'SW3': (165.1, 83.82, 0, 'RESET', {'1': 'BGND', '2': 'EN'}),
        'R14': (165.1, 109.22, 0, '10k', {'1': 'MCU_3V3', '2': 'BOOT'}),
        'SW2': (165.1, 134.62, 0, 'BOOT', {'1': 'BGND', '2': 'BOOT'}),
        'R7': (297.18, 38.1, 0, '4.7k', {'1': 'MCU_3V3', '2': 'SCL'}),
        'R8': (322.58, 38.1, 0, '4.7k', {'1': 'MCU_3V3', '2': 'SDA'}),
        'J3': (302.26, 66.04, 0, 'THERMAL_I2C', {'1': 'SDA', '2': 'SCL', '3': 'BGND', '4': 'MCU_3V3'}),
        'R16': (213.36, 147.32, 90, '330', {'1': 'LED_R', '2': 'LED_R_A'}),
        'R17': (213.36, 160.02, 90, '330', {'1': 'LED_G', '2': 'LED_G_A'}),
        'R18': (213.36, 172.72, 90, '330', {'1': 'LED_B', '2': 'LED_B_A'}),
        'D6': (248.92, 160.02, 0, 'LED_KRGB', {'1': 'BGND', '2': 'LED_R_A', '3': 'LED_G_A', '4': 'LED_B_A'}),
        'R12': (299.72, 104.14, 0, '330', {'1': 'MCU_3V3', '2': '@wire'}),
        'D5': (299.72, 127, 90, 'POWER', {'1': 'BGND', '2': '@wire'}),
        'BZ1': (350.52, 104.14, 180, 'Buzzer (3V3 type TBD)', {'1': 'MCU_3V3', '2': 'BUZZER_LOW'}),
        'Q2': (350.52, 142.24, 0, 'AO3400A', {'1': '@wire', '2': 'BGND', '3': 'BUZZER_LOW'}),
        'R15': (317.5, 142.24, 90, '100', {'1': 'BUZZER_DRIVE', '2': '@wire'}),
        'R26': (330.2, 165.1, 0, '100k', {'1': '@wire', '2': 'BGND'}),
        'R27': (299.72, 165.1, 0, '100k', {'1': 'CTL', '2': 'BGND'}),
    }
    placed = {}
    for ref, (x, y, angle, name, mapping) in cfg.items():
        s = copy.deepcopy(originals.get(ref, originals['R13']))
        if ref not in originals:
            put(s, 'uuid', uid())
        if ref == 'U4':
            put(s, 'lib_id', Quoted(module[1]))
            prop(s, 'Footprint', 'RF_Module:ESP32-S3-WROOM-1')
            prop(s, 'Datasheet', 'https://www.espressif.com/sites/default/files/documentation/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf')
            prop(s, 'Description', 'ESP32-S3 module, 16MB flash, 8MB octal PSRAM, PCB antenna')
            prop(s, 'JLCPCB Part', 'C2913202')
        prop(s, 'Reference', ref)
        prop(s, 'Value', name)
        put(s, 'at', num(x), num(y), num(angle))
        definition = defs[value(s, 'lib_id')]
        s[:] = [p for p in s if not (isinstance(p, list) and p[0] in ('pin', 'mirror'))]
        for p in pins(definition):
            s.append(['pin', Quoted(value(p, 'number')), ['uuid', uid()]])
        for p in children(s, 'property'):
            put(p, 'at', num(x + 3.81), num(y), num(angle % 180))
            put(p, 'effects', ['font', ['size', '1.0', '1.0']], ['justify', 'left'])
            if p[1] == 'Reference':
                put(p, 'at', num(x + 3.81), num(y - 2.54), num(angle % 180))
            elif p[1] == 'Value':
                put(p, 'at', num(x + 3.81), num(y), num(angle % 180))
            else:
                put(p, 'hide', 'yes')
        if ref == 'U4':
            for p in children(s, 'property'):
                if p[1] in ('Reference', 'Value'):
                    put(p, 'at', num(x - 12.7), num(y - (46.99 if p[1] == 'Reference' else 44.45)), '0')
        elif ref == 'D6':
            for p in children(s, 'property'):
                if p[1] in ('Reference', 'Value'):
                    put(p, 'at', num(x + 3.81), num(y - (17.78 if p[1] == 'Reference' else 15.24)), '0')
        elif ref in ('J3', 'BZ1'):
            for p in children(s, 'property'):
                if p[1] in ('Reference', 'Value'):
                    put(p, 'at', num(x - 3.81), num(y - (10.16 if p[1] == 'Reference' else 7.62)), num(angle % 180))
        elif (angle in (90, 270) and ref != 'D5') or ref.startswith('SW'):
            for p in children(s, 'property'):
                if p[1] in ('Reference', 'Value'):
                    put(p, 'at', num(x - 3.81), num(y - (6.35 if p[1] == 'Reference' else 3.81)), num(angle % 180))
        inst = first(s, 'instances')
        for project in children(inst, 'project'):
            for path in children(project, 'path'):
                put(path, 'reference', Quoted(ref))
        sch.append(s)
        placed[ref] = (s, definition)
        connect(sch, s, definition, mapping)

    def point(ref, number):
        s, definition = placed[ref]
        p = next(p for p in pins(definition) if value(p, 'number') == number)
        return pin_position(s, p)[:2]

    sch.append(wire(*point('R12', '2'), *point('D5', '2')))
    gate_join = (330.2, 142.24)
    sch.append(wire(*point('R15', '2'), *gate_join))
    sch.append(wire(*gate_join, *point('Q2', '1')))
    sch.append(wire(*gate_join, *point('R26', '1')))
    sch.append(['junction', ['at', num(gate_join[0]), num(gate_join[1])], ['diameter', '0'], ['color', '0', '0', '0', '0'], ['uuid', uid()]])

    for x, y, text in [
        (147.32, 15.24, 'MCU MODULE REVISION - power/relay/ADC/USB sections at left remain under review'),
        (226.06, 127, 'GPIO35-37 reserved for octal PSRAM; unused pins intentionally NC'),
        (226.06, 132.08, 'SDA moved from strapping GPIO3 to GPIO10; UART uses GPIO43/44'),
        (185.42, 190.5, 'BOOT: hold SW2, press/release RESET SW3, then release SW2 to enter download mode'),
        (185.42, 198.12, 'D6 footprint mismatch and unspecified buzzer/fuse ratings still block fabrication'),
    ]:
        sch.append(['text', Quoted(text), ['at', num(x), num(y), '0'],
                    ['effects', ['font', ['size', '1.27', '1.27']], ['justify', 'left']], ['uuid', uid()]])
    save(STAGE / BOARD.with_suffix('.kicad_sch'), sch)
    kept = set(originals) - region_refs | set(cfg)
    info = {'kept_refs': sorted(kept), 'removed_refs': sorted(region_refs - set(cfg)), 'module_map': MODULE_MAP}
    (STAGE / 'migration.json').write_text(json.dumps(info, indent=2) + '\n')
    print(json.dumps(info, indent=2))


if __name__ == '__main__':
    make_schematic()
