"""Find short ground stitches with clearance on both outer layers."""
import sys,math,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import *
b=parse(ROOT/'smart_db.kicad_pcb');rects=[];lines=[];targets={};own=[]
def clearance(net):return .5 if net in ['LOAD_IN','LOAD_OUT'] else .25 if net in ['LOGIC_5V_FUSED','LOGIC_5V_IN','RELAY_LOW'] else .2
for f in children(b,'footprint'):
    at=first(f,'at');fx,fy=map(float,at[1:3]);a=math.radians(float(at[3]) if len(at)>3 else 0)
    for p in children(f,'pad'):
        if not set(first(p,'layers')[1:])&{'*.Cu','F.Cu','B.Cu'}:continue
        q=first(p,'at');px,py=map(float,q[1:3]);x=fx+math.cos(a)*px+math.sin(a)*py;y=fy-math.sin(a)*px+math.cos(a)*py
        w,h=map(float,first(p,'size')[1:3]);pa=math.radians(float(q[3]) if len(q)>3 else 0)
        hx=(abs(math.cos(pa))*w+abs(math.sin(pa))*h)/2;hy=(abs(math.sin(pa))*w+abs(math.cos(pa))*h)/2
        targets[props(f)['Reference'],p[1]]=(x,y)
        if value(p,'net')=='BGND':own.append((x,y,hx,hy));continue
        rects.append((x,y,hx,hy,clearance(value(p,'net'))))
for v in children(b,'via'):
    if value(v,'net')!='BGND':
        x,y=map(float,first(v,'at')[1:3]);r=float(value(v,'size'))/2
        rects.append((x,y,r,r,clearance(value(v,'net'))))
for t in children(b,'segment'):
    if value(t,'net')!='BGND':lines.append((list(map(float,first(t,'start')[1:3])),list(map(float,first(t,'end')[1:3])),float(value(t,'width'))/2+clearance(value(t,'net')),value(t,'layer')))
rs=np.array(rects);ow=np.array(own)
def free(points,r,front=False):
    ps=np.array(points)
    if np.any((abs(ps[:,None,0]-rs[None,:,0])<rs[None,:,2]+rs[None,:,4]+r+.015)&(abs(ps[:,None,1]-rs[None,:,1])<rs[None,:,3]+rs[None,:,4]+r+.015)):return False
    for a,c,w,layer in lines:
        if front and layer!='F.Cu':continue
        a=np.array(a);d=np.array(c)-a;u=np.clip(((ps-a)*d).sum(axis=1)/(d@d or 1),0,1)
        if np.any(np.linalg.norm(ps-a-u[:,None]*d,axis=1)<w+r+.015):return False
    return True
paths=[]
for key in [('D6','5'),('R20','2')]:
    a=targets[key];found=False
    for radius in np.arange(.8,4,.1):
        for angle in np.arange(0,2*math.pi,math.pi/16):
            p=(round(a[0]+radius*math.cos(angle),3),round(a[1]+radius*math.sin(angle),3))
            if np.any((abs(p[0]-ow[:,0])<ow[:,2]+.25)&(abs(p[1]-ow[:,1])<ow[:,3]+.25)):continue
            if free([p],.3) and free(np.linspace(a,p,max(2,math.ceil(radius/.03))),.15,True):
                paths.append([a,p]);found=True;break
        if found:break
    assert found,('No ground stitch',key)
(ROOT/'work/ground_stitches.json').write_text(json.dumps(paths,indent=2)+'\n')
print(paths)
