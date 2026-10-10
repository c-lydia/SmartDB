"""Find conservative B.Cu supply paths; KiCad DRC is the final geometry check."""
import heapq, json, math, sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import *
b=parse(ROOT/'smart_db.kicad_pcb')
STEP=.1; X0=60; Y0=47
xs=X0+np.arange(951)*STEP;ys=Y0+np.arange(781)*STEP
blocked=np.zeros((len(xs),len(ys)),dtype=bool)
blocked[:6,:]=True;blocked[-6:,:]=True;blocked[:,:6]=True;blocked[:,-6:]=True
def box(x,y,hx,hy,margin):
    ix=np.where(abs(xs-x)<=hx+margin)[0];iy=np.where(abs(ys-y)<=hy+margin)[0]
    blocked[np.ix_(ix,iy)]=True
def circle(x,y,r):
    ix=np.where(abs(xs-x)<=r)[0];iy=np.where(abs(ys-y)<=r)[0]
    blocked[np.ix_(ix,iy)] |= (xs[ix,None]-x)**2+(ys[None,iy]-y)**2<=r*r
def line(a,c,r):
    x1,y1=map(float,a);x2,y2=map(float,c)
    ix=np.where((xs>=min(x1,x2)-r)&(xs<=max(x1,x2)+r))[0]
    iy=np.where((ys>=min(y1,y2)-r)&(ys<=max(y1,y2)+r))[0]
    dx=x2-x1;dy=y2-y1
    t=np.clip(((xs[ix,None]-x1)*dx+(ys[None,iy]-y1)*dy)/(dx*dx+dy*dy or 1),0,1)
    blocked[np.ix_(ix,iy)] |= (xs[ix,None]-x1-t*dx)**2+(ys[None,iy]-y1-t*dy)**2<=r*r
for x,y in [(64,51),(151,51),(64,121),(151,121)]:circle(x,y,3.8)
box(85,37,26.6,10.7,.3)  # antenna region
box(60,83,4.51,4.57,.6) # USB cutout
for f in children(b,'footprint'):
    at=first(f,'at');fx,fy=map(float,at[1:3]);a=math.radians(float(at[3]) if len(at)>3 else 0)
    for p in children(f,'pad'):
        if value(p,'net')=='VCC':continue
        if not set(first(p,'layers')[1:]) & {'*.Cu','B.Cu'}:continue
        q=first(p,'at');px,py=map(float,q[1:3]);x=fx+math.cos(a)*px+math.sin(a)*py;y=fy-math.sin(a)*px+math.cos(a)*py
        w,h=map(float,first(p,'size')[1:3]);pa=math.radians(float(q[3]) if len(q)>3 else 0)
        hx=(abs(math.cos(pa))*w+abs(math.sin(pa))*h)/2;hy=(abs(math.sin(pa))*w+abs(math.cos(pa))*h)/2
        margin=.85 if value(p,'net') in ['LOAD_IN','LOAD_OUT'] else .6
        box(x,y,hx,hy,margin)
for v in children(b,'via'):
    if value(v,'net')!='VCC':circle(*map(float,first(v,'at')[1:3]),float(value(v,'size'))/2+.6)
for t in children(b,'segment'):
    if value(t,'layer')=='B.Cu' and value(t,'net')!='VCC':
        line(first(t,'start')[1:3],first(t,'end')[1:3],float(value(t,'width'))/2+.6)
def idx(p):return (round((p[0]-X0)/STEP),round((p[1]-Y0)/STEP))
def route(a,c):
    start,end=idx(a),idx(c)
    assert not blocked[start],('blocked start',a)
    assert not blocked[end],('blocked end',c)
    heap=[(0,start)];dist={start:0};prev={}
    while heap:
        _,p=heapq.heappop(heap)
        if p==end:break
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
            q=(p[0]+dx,p[1]+dy)
            if not (0<=q[0]<len(xs) and 0<=q[1]<len(ys)) or blocked[q]:continue
            if dx and dy and (blocked[p[0]+dx,p[1]] or blocked[p[0],p[1]+dy]):continue
            nd=dist[p]+(math.sqrt(2) if dx and dy else 1)
            if nd<dist.get(q,float('inf')):
                dist[q]=nd;prev[q]=p;heapq.heappush(heap,(nd+math.hypot(q[0]-end[0],q[1]-end[1]),q))
    else:raise RuntimeError(('No clear power path',a,c))
    path=[end]
    while path[-1]!=start:path.append(prev[path[-1]])
    path.reverse();simple=[path[0]]
    for i in range(1,len(path)-1):
        if (path[i][0]-path[i-1][0],path[i][1]-path[i-1][1])!=(path[i+1][0]-path[i][0],path[i+1][1]-path[i][1]):simple.append(path[i])
    simple.append(path[-1]);points=[[round(X0+x*STEP,4),round(Y0+y*STEP,4)] for x,y in simple]
    points[0]=list(a);points[-1]=list(c)
    return points
def clear_segment(a,c):
    samples=np.linspace(a,c,max(2,math.ceil(math.dist(a,c)/.035)))
    ix=np.rint((samples[:,0]-X0)/STEP).astype(int);iy=np.rint((samples[:,1]-Y0)/STEP).astype(int)
    return not blocked[ix,iy].any()
def smooth(points):
    out=[points[0]];i=0
    while i<len(points)-1:
        a=points[i]
        for j in range(len(points)-1,i,-1):
            c=points[j];dx=c[0]-a[0];dy=c[1]-a[1];d=min(abs(dx),abs(dy));sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
            bends=[[a[0]+sx*d,a[1]+sy*d],[c[0]-sx*d,c[1]-sy*d],[a[0],c[1]],[c[0],a[1]]]
            good=next((p for p in bends if clear_segment(a,p) and clear_segment(p,c)),None)
            if good is not None:
                if math.dist(a,good)>.001:out.append(good)
                if math.dist(out[-1],c)>.001:out.append(c)
                i=j;break
        else:raise RuntimeError('Cannot simplify path')
    return out
connections=[((119,117),(79.075,86.3)),((79.075,86.3),(73.1,62.3)),((119,117),(145,74))]
paths=[smooth(route(a,c)) for a,c in connections]
(ROOT/'work/power_paths.json').write_text(json.dumps(paths,indent=2)+'\n')
print('Supply paths generated:',[len(p) for p in paths])
