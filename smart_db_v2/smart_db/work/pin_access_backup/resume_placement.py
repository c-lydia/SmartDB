"""Apply the compact board's placement corrections using KiCad's Python runtime.

Paths are relative to this script. Refuses to move components after routing starts.
The original saved board is preserved in resume_backup/.
"""
import json
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
BOARD = ROOT / "smart_db.kicad_pcb"
sys.path.insert(0, str(ROOT / "work" / "helpers" / "module_update"))
from cad_edit import children, first, parse, props, save

# Remove zero-length silk segments without the SWIG child-ownership ambiguity.
tree = parse(BOARD)
if children(tree, "segment") or children(tree, "via") or children(tree, "arc"):
    raise SystemExit("Placement script cannot run after routing has started.")
module = next(f for f in children(tree, "footprint") if props(f)["Reference"] == "U4")
for line in children(module, "fp_line"):
    if first(line, "start")[1:] == first(line, "end")[1:]:
        module.remove(line)
save(BOARD, tree)
b = pcbnew.LoadBoard(str(BOARD))
if list(b.GetTracks()):
    raise SystemExit("Placement script cannot run after routing has started.")


def point(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


positions = {
    "D1": (120, 96, 90),
    "C11": (76, 69.8, 90),
    "R13": (76, 73.3, 0),
    "C3": (137, 69, 0),
    "C20": (145, 79.5, 0),
}
for f in b.GetFootprints():
    if f.GetReference() in positions:
        x, y, angle = positions[f.GetReference()]
        f.SetOrientationDegrees(angle)
        f.SetPosition(point(x, y))
b.BuildConnectivity()
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
pcbnew.SaveBoard(str(BOARD), b)
actual = {
    f.GetReference(): [pcbnew.ToMM(f.GetPosition().x),
                       pcbnew.ToMM(f.GetPosition().y), f.GetOrientationDegrees()]
    for f in b.GetFootprints()
}
(ROOT / "work" / "positions.json").write_text(json.dumps(actual, indent=2) + "\n")
print("Corrected placement and refilled zones.")
