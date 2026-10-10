import copy
import json
import xml.etree.ElementTree as ET

from cad_edit import *


def load_footprint(library_id):
    library, name = library_id.split(':', 1)
    result = copy.deepcopy(parse(FOOTPRINTS / (library + '.pretty') / (name + '.kicad_mod')))
    result[1] = Quoted(library_id)
    result[:] = [n for n in result if not (isinstance(n, list) and n[0] in ('version', 'generator', 'generator_version'))]
    return result


def refresh_uuids(node):
    for child in node:
        if isinstance(child, list):
            if child and child[0] == 'uuid':
                child[1] = uid()
            else:
                refresh_uuids(child)


def main():
    board = parse(SOURCE / BOARD.with_suffix('.kicad_pcb'))
    sch = parse(STAGE / BOARD.with_suffix('.kicad_sch'))
    symbols = {props(s)['Reference']: s for s in children(sch, 'symbol')}
    old_footprints = {props(f)['Reference']: f for f in children(board, 'footprint')}
    netlist = ET.parse(STAGE / 'netlist.xml')
    nets = {}
    for net in netlist.findall('./nets/net'):
        for node in net.findall('node'):
            # KiCad's PCB format escapes a slash inside a sheet-local net name.
            name = net.get('name').replace('/', '{slash}')
            nets[(node.get('ref'), node.get('pin'))] = (name, node.get('pinfunction'), node.get('pintype'))

    moves = {'U4': (91.05, 61.95, 0), 'C9': (77.5, 58.0, 0),
             'C10': (77.5, 61.5, 0), 'R13': (77.5, 65.0, 0), 'C11': (77.5, 68.5, 0),
             'R26': (109, 82.5, 0), 'R27': (129, 73.5, 0), 'J3': (65, 74, 0)}
    replace = {'U4', 'SW2', 'SW3', 'C9', 'C10', 'C11', 'R13', 'J3'}
    changed_nets = set()
    for ref, old in old_footprints.items():
        for pad in children(old, 'pad'):
            old_net = value(pad, 'net')
            if not old_net:
                continue
            target_net = nets.get((ref, str(pad[1])), ('', None, None))[0]
            if ref not in symbols or ref in moves or ref in replace or old_net != target_net:
                changed_nets.add(str(old_net))

    for old in children(board, 'footprint'):
        board.remove(old)
    for ref, symbol in symbols.items():
        properties = props(symbol)
        old = old_footprints.get(ref)
        if old is None or ref in replace:
            footprint = load_footprint(properties['Footprint'])
            refresh_uuids(footprint)
            put(footprint, 'uuid', value(old, 'uuid') if old is not None else uid())
            if old is not None:
                put(footprint, 'at', *first(old, 'at')[1:])
            else:
                put(footprint, 'at', *map(num, moves[ref]))
        else:
            footprint = copy.deepcopy(old)
        if ref in moves:
            put(footprint, 'at', *map(num, moves[ref]))
        put(footprint, 'layer', Quoted('F.Cu'))
        put(footprint, 'path', Quoted('/' + value(symbol, 'uuid')))
        put(footprint, 'sheetname', Quoted('/'))
        put(footprint, 'sheetfile', Quoted('smart_db.kicad_sch'))
        for key in ('Reference', 'Value', 'Datasheet', 'Description'):
            p = prop(footprint, key, properties.get(key, ''))
            if key in ('Datasheet', 'Description'):
                put(p, 'at', '0', '0', '0')
                put(p, 'layer', Quoted('F.Fab'))
                put(p, 'hide', 'yes')
                put(p, 'effects', ['font', ['size', '1', '1'], ['thickness', '0.15']])
                if first(p, 'uuid') is None:
                    put(p, 'uuid', uid())
        if ref == 'U4':
            put(next(p for p in children(footprint, 'property') if p[1] == 'Reference'), 'at', '12', '0', '0')
            p = prop(footprint, 'JLCPCB Part', 'C2913202')
            p.extend([['at', '0', '0', '0'], ['layer', Quoted('F.Fab')], ['hide', 'yes'], ['uuid', uid()], ['effects', ['font', ['size', '1', '1'], ['thickness', '0.15']]]])
        elif ref == 'D6':
            put(next(p for p in children(footprint, 'property') if p[1] == 'Reference'), 'at', '0', '4.3', '0')
        for pad in children(footprint, 'pad'):
            if not pad[1]:
                continue
            key = (ref, str(pad[1]))
            if key not in nets:
                continue  # Original extra pads (e.g. D6/J4) remain an explicit review issue.
            net, function, kind = nets[key]
            put(pad, 'net', Quoted(net))
            if function:
                put(pad, 'pinfunction', Quoted(function))
            if kind:
                put(pad, 'pintype', Quoted(kind))
        board.append(footprint)

    removed_tracks = 0
    removed_vias = 0
    for kind in ('segment', 'via'):
        for item in children(board, kind):
            if value(item, 'net') in changed_nets:
                board.remove(item)
                if kind == 'segment':
                    removed_tracks += 1
                else:
                    removed_vias += 1
    board.append(['gr_text', Quoted('ESP32-S3 MODULE MIGRATION - ROUTING DRAFT\nPower/relay/ADC/USB review and board outline still required'),
                  ['at', '122', '144', '0'], ['layer', Quoted('Dwgs.User')], ['uuid', uid()],
                  ['effects', ['font', ['size', '1.2', '1.2'], ['thickness', '0.2']]]])
    save(STAGE / BOARD.with_suffix('.kicad_pcb'), board)
    summary = {'removed_obsolete_tracks': removed_tracks, 'removed_obsolete_vias': removed_vias,
               'retained_tracks': len(children(board, 'segment')), 'footprints': len(children(board, 'footprint')),
               'affected_old_nets': sorted(changed_nets), 'moved_footprints': moves}
    (STAGE / 'pcb_migration.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
