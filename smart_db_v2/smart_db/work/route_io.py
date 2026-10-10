"""Exchange local Specctra routing data with KiCad; inner layers stay ground planes."""
import sys
import json
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parent.parent
b = pcbnew.LoadBoard(str(ROOT / 'smart_db.kicad_pcb'))
if sys.argv[1] == 'export':
    assert pcbnew.ExportSpecctraDSN(b, str(ROOT / 'work/connectors.dsn'))
    pads = []
    for f in b.GetFootprints():
        for p in f.Pads():
            pads.append({'ref': f.GetReference(), 'pin': p.GetNumber(), 'net': p.GetNetname(),
                         'xy': [pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)]})
    (ROOT / 'work/pads_current.json').write_text(json.dumps(pads, indent=2))
elif sys.argv[1] == 'import':
    assert pcbnew.ImportSpecctraSES(b, str(ROOT / 'work/connectors.ses'))
    for t in b.GetTracks():
        if not isinstance(t, pcbnew.PCB_VIA):
            assert t.GetLayer() in [pcbnew.F_Cu, pcbnew.B_Cu], 'Signal on inner plane'
    b.BuildConnectivity()
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())
    pcbnew.SaveBoard(str(ROOT / 'smart_db.kicad_pcb'), b)
print(sys.argv[1], 'complete')
