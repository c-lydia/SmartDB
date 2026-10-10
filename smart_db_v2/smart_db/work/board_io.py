import pcbnew,sys,json,math
from pathlib import Path
root=Path('/tmp/smartdb_review/compact');p=root/'smart_db_v2/smart_db/smart_db.kicad_pcb';b=pcbnew.LoadBoard(str(p))
def pt(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))
def zone(net,layer,points,keepout=False):
 z=pcbnew.ZONE(b);z.SetLayer(layer)
 if keepout:
  z.SetIsRuleArea(True);z.SetLayerSet(pcbnew.LSET.AllCuMask());z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(True)
 else:
  z.SetNetCode(b.FindNet(net).GetNetCode());z.SetLocalClearance(pcbnew.FromMM(.25));z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL);z.SetMinThickness(pcbnew.FromMM(.2))
 o=z.Outline();o.NewOutline()
 for x,y in points:o.Append(pcbnew.FromMM(x),pcbnew.FromMM(y))
 b.Add(z)
if sys.argv[1]=='place':
 positions=json.loads((root/'positions.json').read_text())
 for f in b.GetFootprints():
  x,y,a=positions[f.GetReference()];f.SetOrientationDegrees(a);f.SetPosition(pt(x,y))
  if f.GetReference()=='U4':
   for z in f.Zones():z.SetLayerSet(pcbnew.LSET.AllCuMask())
 # The USB footprint supplies the inner notch edges.
 outline=[(67.64,76.3),(60,76.3),(60,47),(155,47),(155,125),(60,125),(60,89.7),(67.64,89.7)]
 for a,c in zip(outline,outline[1:]):
  n=pcbnew.PCB_SHAPE(b);n.SetShape(pcbnew.SHAPE_T_SEGMENT);n.SetStart(pt(*a));n.SetEnd(pt(*c));n.SetLayer(pcbnew.Edge_Cuts);n.SetWidth(pcbnew.FromMM(.05));b.Add(n)
 for layer in [pcbnew.F_Cu,pcbnew.In1_Cu,pcbnew.In2_Cu,pcbnew.B_Cu]:zone('BGND',layer,[(60.4,47.4),(154.6,47.4),(154.6,124.6),(60.4,124.6)])
 for x,y in [(64,51),(151,51),(64,121),(151,121)]:zone('',pcbnew.F_Cu,[(x+3.4*math.cos(i*math.pi/16),y+3.4*math.sin(i*math.pi/16)) for i in range(32)],True)
 b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(p),b)
 print('Placed compact board, two internal ground planes, four M3 keepouts.')
elif sys.argv[1]=='adjust':
 positions=json.loads((root/'positions.json').read_text())
 for f in b.GetFootprints():
  x,y,a=positions[f.GetReference()];f.SetOrientationDegrees(a);f.SetPosition(pt(x,y))
  if f.GetReference()=='U4':
   for g in f.GraphicalItems():
    if g.GetLayer()==pcbnew.F_SilkS and hasattr(g,'GetStart') and hasattr(g,'GetEnd'):
     a,c=g.GetStart(),g.GetEnd();ay,cy=pcbnew.ToMM(a.y),pcbnew.ToMM(c.y)
     if ay<47.3 and cy<47.3:g.SetLayer(pcbnew.F_Fab)
     elif ay<47.3:g.SetStart(pt(pcbnew.ToMM(a.x),47.3))
     elif cy<47.3:g.SetEnd(pt(pcbnew.ToMM(c.x),47.3))
 b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(p),b);print('Adjusted placement')
elif sys.argv[1]=='fill':
 b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(p),b);print('Filled')
elif sys.argv[1]=='export':
 b.BuildConnectivity();assert pcbnew.ExportSpecctraDSN(b,str(root/'route.dsn'));print('Exported')
elif sys.argv[1]=='import':
 assert pcbnew.ImportSpecctraSES(b,str(root/'route.ses'))
 for t in b.GetTracks():
  if not isinstance(t,pcbnew.PCB_VIA) and t.GetWidth()<pcbnew.FromMM(.2):t.SetWidth(pcbnew.FromMM(.2))
 b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(p),b);print('Imported and filled')
