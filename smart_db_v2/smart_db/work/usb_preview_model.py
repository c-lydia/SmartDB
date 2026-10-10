"""Create a simplified USB-C visualization, not a manufacturing/mechanical model.

Shell envelope follows the KiCad footprint and Amphenol 12401948 product drawing.
The manufacturer's downloadable STEP was unavailable (HTTP 403). The local model
shows opening, tongue, shell and mounting tabs, and is explicitly approximate.
"""
import math
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'work/helpers/module_update'))
from cad_edit import *

out = ['#VRML V2.0 utf8', '# Approximate visualization only; dimensions in 0.1 inch units.']
def mesh(points, faces, color):
    xyz = ',\n'.join(' '.join(f'{v/2.54:.6f}' for v in p) for p in points)
    indices = ',\n'.join(' '.join(map(str, f)) + ' -1' for f in faces)
    out.append(f'Shape {{ appearance Appearance {{ material Material {{ diffuseColor {color} }} }} geometry IndexedFaceSet {{ solid FALSE coord Coordinate {{ point [{xyz}] }} coordIndex [{indices}] }} }}')
def box(x,y,z,w,d,h,color):
    points=[(x+dx*w/2,y+dy*d/2,z+dz*h/2) for dz in [-1,1] for dy in [-1,1] for dx in [-1,1]]
    mesh(points, [[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]], color)
def profile(radius):
    return [(sx*2.89+radius*math.cos(a),.65+radius*math.sin(a))
            for sx,start in [(1,-math.pi/2),(-1,math.pi/2)]
            for a in [start+i*math.pi/12 for i in range(13)]]
outer,inner=profile(1.58),profile(1.33)
points=[(x,y,z) for y in [-5.85,5.22] for ring in [outer,inner] for x,z in ring]
n=len(outer);faces=[]
for i in range(n):
    j=(i+1)%n
    faces.extend([[i,j,2*n+j,2*n+i],[n+i,3*n+i,3*n+j,n+j],
                  [i,n+i,n+j,j],[2*n+i,2*n+j,3*n+j,3*n+i]])
mesh(points,faces,'0.7 0.72 0.74')
box(0,3.5,.65,8,2.9,2.3,'0.07 0.07 0.08')
box(0,-1.5,.65,6.7,7.2,.7,'0.08 0.08 0.09')
for x in [-2.5,-1.75,-1.25,-.75,-.25,.25,.75,1.25,1.75,2.5]:
    box(x,-3.9,1.025,.25,2.1,.06,'0.78 0.62 0.2')
for x,y in [(-5.92,0),(5.92,0),(-4.65,4.32),(4.65,4.32)]:
    box(x,y,-.6,.3,1.15,3.5,'0.7 0.72 0.74')
modeldir=ROOT/'SmartDB.3dshapes';modeldir.mkdir(exist_ok=True)
(modeldir/'USB_C_12401948_preview.wrl').write_text('\n'.join(out)+'\n')
libpath=next(Path('/var/lib/flatpak/runtime/org.kicad.KiCad.Library.Footprints').glob('x86_64/stable/*/files/footprints/Connector_USB.pretty/USB_C_Receptacle_Amphenol_12401948E412A.kicad_mod'))
lib=parse(libpath);lib[1]=Quoted('USB_C_Receptacle_Amphenol_12401948E412A_Preview')
board=parse(ROOT/'smart_db.kicad_pcb')
f=next(f for f in children(board,'footprint') if props(f)['Reference']=='J4')
f[1]=Quoted('SmartDB:'+str(lib[1]))
for node in [lib,f]:
    first(node,'model')[1]=Quoted('${KIPRJMOD}/SmartDB.3dshapes/USB_C_12401948_preview.wrl')
save(ROOT/'SmartDB.pretty'/f'{lib[1]}.kicad_mod',lib)
save(ROOT/'smart_db.kicad_pcb',board)
sch=parse(ROOT/'smart_db.kicad_sch')
s=next(s for s in children(sch,'symbol') if props(s)['Reference']=='J4')
prop(s,'Footprint',str(f[1]));save(ROOT/'smart_db.kicad_sch',sch)
print('Added explicitly approximate, project-local USB connector visualization.')
