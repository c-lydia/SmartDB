"""Package only reviewed permanent CAD and its project-local dependencies."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / 'smart_db_v2/smart_db'


def prepare():
    record = json.loads((BOARD / 'work/validation_current.json').read_text())
    mismatches = []
    for name, expected in record['sha256'].items():
        path = BOARD / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            mismatches.append(name)
    if mismatches:
        raise RuntimeError('CAD validation manifest is stale; review these files before publishing: ' + ', '.join(mismatches))
    paths = [BOARD / name for name in ('smart_db.kicad_pcb', 'smart_db.kicad_sch',
        'smart_db.kicad_pro', 'SmartDB.kicad_sym', 'fp-lib-table', 'sym-lib-table', 'README.md',
        'smart_db.step', 'work/validation_current.json', 'work/erc_current.json',
        'work/drc_routing_current.json', 'work/routing_review.md', 'work/camera_power_review.json',
        'work/schematic_current.pdf', 'work/routing_current.pdf', 'work/placement_current.pdf',
        'work/back_labels_current.pdf')]
    for folder in ('SmartDB.pretty', 'SmartDB.3dshapes'):
        paths.extend(p for p in (BOARD / folder).rglob('*') if p.is_file())
    paths.extend([BOARD.parent / 'pinmap.csv', BOARD.parent / 'README.md'])
    output = ROOT / 'docs/_build/artifacts/smartdb-v2.zip'
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            archive.write(path, path.relative_to(ROOT))
    print(f'Packaged {len(paths)} current PCB files; {len(record["sha256"])} validation hashes matched.')


if __name__ == '__main__':
    prepare()
