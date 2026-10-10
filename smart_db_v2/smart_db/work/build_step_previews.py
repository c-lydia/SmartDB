"""Build simplified visual models, NOT certified mechanical-fit models.

Run with cadquery-ocp-novtk==7.9.3.1.1. Units: mm.
D6 envelope: ROHM short-form 2023 p263. USB: existing local preview dimensions.
This script only creates models; it never changes PCB copper or placement.
"""
from pathlib import Path
from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder
from OCP.BRepAlgoAPI import BRepAlgoAPI_Fuse, BRepAlgoAPI_Cut
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax2
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ColorType
from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
from OCP.STEPCAFControl import STEPCAFControl_Writer
from OCP.STEPControl import STEPControl_AsIs
from OCP.IFSelect import IFSelect_RetDone

OUT = Path(__file__).resolve().parent.parent / 'SmartDB.3dshapes'
SILVER = (.70, .72, .74)
BLACK = (.07, .07, .08)
GOLD = (.78, .62, .20)
def box(x, y, z, w, d, h):
    return BRepPrimAPI_MakeBox(gp_Pnt(x-w/2, y-d/2, z-h/2), w, d, h).Shape()
def cylinder(x,y,z,r,h,direction=(0,1,0)):
    return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x,y,z), gp_Dir(*direction)),r,h).Shape()
def capsule(radius):
    shape = box(0,(-5.85+5.22)/2,.65,5.78,11.07,2*radius)
    for x in [-2.89,2.89]:
        shape = BRepAlgoAPI_Fuse(shape,cylinder(x,-5.85,.65,radius,11.07)).Shape()
    return shape
def write(name, parts):
    doc = TDocStd_Document(TCollection_ExtendedString('SmartDB simplified preview'))
    shapes = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(doc.Main())
    for label,shape,color in parts:
        assert BRepCheck_Analyzer(shape).IsValid(), label
        item = shapes.AddShape(shape,False)
        TDataStd_Name.Set_s(item,TCollection_ExtendedString(label))
        colors.SetColor(item,Quantity_Color(*color,Quantity_TOC_RGB),XCAFDoc_ColorType.XCAFDoc_ColorGen)
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    assert writer.Transfer(doc,STEPControl_AsIs)
    assert writer.Write(str(OUT/name)) == IFSelect_RetDone
    print(name, 'valid solid parts:', len(parts))

parts=[('Simplified USB shell',BRepAlgoAPI_Cut(capsule(1.58),capsule(1.33)).Shape(),SILVER),
       ('Rear insulator',box(0,3.5,.65,8,2.9,2.3),BLACK),
       ('Tongue',box(0,-1.5,.65,6.7,7.2,.7),BLACK)]
for i,x in enumerate([-2.5,-1.75,-1.25,-.75,-.25,.25,.75,1.25,1.75,2.5]):
    parts.append((f'Preview contact {i}',box(x,-3.9,1.025,.25,2.1,.06),GOLD))
for i,(x,y) in enumerate([(-5.92,0),(5.92,0),(-4.65,4.32),(4.65,4.32)]):
    parts.append((f'Mount tab {i}',box(x,y,-.6,.3,1.15,3.5),SILVER))
write('USB_C_12401948_preview.step',parts)

# Overall lead span 3.5, molded body 3.1 x 2.8, nominal total height .6.
body = box(0,0,.325,3.1,2.8,.55)
recess = box(0,0,.575,2.65,2.3,.15)
parts=[('Simplified SMLVN6 body',BRepAlgoAPI_Cut(body,recess).Shape(),(.92,.91,.85)),
       ('Lens preview',box(0,0,.52,2.65,2.3,.04),(.82,.84,.73))]
for side in [-1,1]:
    for y in [-.95,0,.95]:
        parts.append(('Terminal',box(side*1.35,y,.075,.8,.5,.15),SILVER))
parts.append(('Anode index',box(-1.42,1.22,.605,.15,.15,.01),BLACK))
write('LED_ROHM_SMLVN6_preview.step',parts)
