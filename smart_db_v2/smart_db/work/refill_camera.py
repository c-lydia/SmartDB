"""Refill existing ground zones after the camera-power addition."""
import os
from pathlib import Path
import pcbnew
p=Path(__file__).resolve().parent.parent/'smart_db.kicad_pcb'
b=pcbnew.LoadBoard(str(p))
b.BuildConnectivity()
filler=pcbnew.ZONE_FILLER(b);filler.Fill(b.Zones())
pcbnew.SaveBoard(str(p),b)
print('Ground zones refilled.',flush=True)
os._exit(0)
