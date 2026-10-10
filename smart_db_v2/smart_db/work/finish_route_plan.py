"""Conservative local escape/route planner; all results require KiCad DRC."""
import heapq,json,math,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'work/helpers/module_update'))
from cad_edit import *
b=parse(ROOT/'smart_db.kicad_pcb');pads=[];lines=[];vias=[];targets={}
def clearance(net):return .5 if net in ['LOAD_IN','LOAD_OUT'] else .25 if net in ['LOGIC_5V_FUSED','LOGIC_5V_IN','RELAY_LOW'] else .2
for f in children(b,'footprint'):
    at=first(f,'at');fx,fy=map(float,at[1:3]);a=math.radians(float(at[3]) if len(at)>3 else 0)
    for p in children(f,'pad'):
        layers=set(first(p,'layers')[1:]);net=value(p,'net')
        q=first(p,'at');px,py=map(float,q[1:3]);x=fx+math.cos(a)*px+math.sin(a)*py;y=fy-math.sin(a)*px+math.cos(a)*py
        w,h=map(float,first(p,'size')[1:3]);pa=math.radians(float(q[3]) if len(q)>3 else 0)
        hx=(abs(math.cos(pa))*w+abs(math.sin(pa))*h)/2;hy=(abs(math.sin(pa))*w+abs(math.cos(pa))*h)/2
        key=(props(f)['Reference'],p[1]);targets[key]=(x,y)
        if '*.Cu' in layers:layers={'F.Cu','B.Cu'}
        pads.append((x,y,hx,hy,net,layers,key))
for v in children(b,'via'):
    x,y=map(float,first(v,'at')[1:3]);vias.append((x,y,float(value(v,'size'))/2,value(v,'net')))
for t in children(b,'segment'):
    lines.append((np.array(first(t,'start')[1:3],float),np.array(first(t,'end')[1:3],float),float(value(t,'width'))/2,value(t,'net'),value(t,'layer')))
def free(points,r,net,layer=None):
    ps=np.array(points)
    if np.any((ps[:,0]<60.7)|(ps[:,0]>154.3)|(ps[:,1]<48)|(ps[:,1]>124.3)):return False
    for x,y,hx,hy,n,ls,k in pads:
        if n==net or (layer and layer not in ls):continue
        margin=max(.2,clearance(n))+r+.025
        if np.any((abs(ps[:,0]-x)<hx+margin)&(abs(ps[:,1]-y)<hy+margin)):return False
    for x,y,rad,n in vias:
        if n!=net and np.any(np.linalg.norm(ps-[x,y],axis=1)<rad+r+max(.2,clearance(n))+.025):return False
    for a,c,rad,n,l in lines:
        if n==net or (layer and layer!=l):continue
        d=c-a;u=np.clip(((ps-a)*d).sum(axis=1)/(d@d or 1),0,1)
        if np.any(np.linalg.norm(ps-a-u[:,None]*d,axis=1)<rad+r+max(.2,clearance(n))+.025):return False
    return True
def escape(a,net):
    for radius in np.arange(.8,5,.1):
        for angle in np.arange(0,2*math.pi,math.pi/16):
            p=(round(a[0]+radius*math.cos(angle),3),round(a[1]+radius*math.sin(angle),3))
            if any(n==net and abs(p[0]-x)<hx+.35 and abs(p[1]-y)<hy+.35 for x,y,hx,hy,n,ls,k in pads):continue
            if free([p],.3,net) and free(np.linspace(a,p,max(2,math.ceil(radius/.025))),.1,net,'F.Cu'):return p,[a,p]
    for radius in np.arange(1,6,.25):
        for angle in np.arange(0,2*math.pi,math.pi/8):
            p=(round(a[0]+radius*math.cos(angle),3),round(a[1]+radius*math.sin(angle),3))
            if any(n==net and abs(p[0]-x)<hx+.35 and abs(p[1]-y)<hy+.35 for x,y,hx,hy,n,ls,k in pads):continue
            if free([p],.3,net):
                try:return p,route(a,p,net,'F.Cu')
                except (RuntimeError,AssertionError):pass
    raise RuntimeError(('No escape',net,a))
STEP=.05;X0=60;Y0=47;xs=X0+np.arange(1901)*STEP;ys=Y0+np.arange(1561)*STEP
def route(a,c,net,layer='B.Cu',grid_only=False,track_width=None,via_grid=False):
    blocked=np.zeros((len(xs),len(ys)),bool)
    blocked[:14,:]=True;blocked[-14:,:]=True;blocked[:,:20]=True;blocked[:,-14:]=True
    def box(x,y,hx,hy,margin):
        ix=np.where(abs(xs-x)<=hx+margin)[0];iy=np.where(abs(ys-y)<=hy+margin)[0];blocked[np.ix_(ix,iy)]=True
    def segment(a,c,r):
        x1,y1=a;x2,y2=c;ix=np.where((xs>=min(x1,x2)-r)&(xs<=max(x1,x2)+r))[0];iy=np.where((ys>=min(y1,y2)-r)&(ys<=max(y1,y2)+r))[0]
        dx=x2-x1;dy=y2-y1;u=np.clip(((xs[ix,None]-x1)*dx+(ys[None,iy]-y1)*dy)/(dx*dx+dy*dy or 1),0,1)
        blocked[np.ix_(ix,iy)] |= (xs[ix,None]-x1-u*dx)**2+(ys[None,iy]-y1-u*dy)**2<=r*r
    for x,y in [(64,51),(151,51),(64,121),(151,121)]:box(x,y,3.4,3.4,.1)
    box(85,37,26.6,10.7,.3);box(60,83,4.51,4.57,.6)
    radius=.3 if via_grid else track_width/2 if track_width is not None else .15 if layer=='B.Cu' else .1
    for x,y,hx,hy,n,ls,k in pads:
        if n!=net and (via_grid or layer in ls):box(x,y,hx,hy,max(.2,clearance(n))+radius+.025)
    for x,y,r,n in vias:
        if n!=net:segment((x,y),(x,y),r+max(.2,clearance(n))+radius+.025)
    for p,q,r,n,l in lines:
        if n!=net and (via_grid or l==layer):segment(p,q,r+max(.2,clearance(n))+radius+.025)
    if grid_only:return blocked
    def idx(p):return round((p[0]-X0)/STEP),round((p[1]-Y0)/STEP)
    start,end=idx(a),idx(c);assert not blocked[start] and not blocked[end],(net,'blocked endpoint')
    heap=[(0,start)];dist={start:0};prev={};visited=set()
    while heap:
        _,p=heapq.heappop(heap)
        if p in visited:continue
        visited.add(p)
        if p==end:break
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
            q=p[0]+dx,p[1]+dy
            if not (0<=q[0]<len(xs) and 0<=q[1]<len(ys)) or blocked[q]:continue
            if dx and dy and (blocked[p[0]+dx,p[1]] or blocked[p[0],p[1]+dy]):continue
            nd=dist[p]+(math.sqrt(2) if dx and dy else 1)
            if nd<dist.get(q,float('inf')):
                dist[q]=nd;prev[q]=p;heapq.heappush(heap,(nd+math.hypot(q[0]-end[0],q[1]-end[1]),q))
    else:raise RuntimeError(('No path',net))
    points=[end]
    while points[-1]!=start:points.append(prev[points[-1]])
    points.reverse();points=[[round(X0+x*STEP,4),round(Y0+y*STEP,4)] for x,y in points];points[0]=list(a);points[-1]=list(c)
    def clear(p,q):
        ps=np.linspace(p,q,max(2,math.ceil(math.dist(p,q)/.02)));ix=np.rint((ps[:,0]-X0)/STEP).astype(int);iy=np.rint((ps[:,1]-Y0)/STEP).astype(int)
        return not blocked[ix,iy].any()
    out=[points[0]];i=0
    while i<len(points)-1:
        p=points[i]
        for j in range(len(points)-1,i,-1):
            q=points[j];dx=q[0]-p[0];dy=q[1]-p[1];d=min(abs(dx),abs(dy));sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
            bends=[[p[0]+sx*d,p[1]+sy*d],[q[0]-sx*d,q[1]-sy*d],[p[0],q[1]],[q[0],p[1]]]
            bend=next((v for v in bends if clear(p,v) and clear(v,q)),None)
            if bend is not None:
                if math.dist(p,bend)>.001:out.append(bend)
                if math.dist(out[-1],q)>.001:out.append(q)
                i=j;break
        else:raise RuntimeError('Cannot simplify')
    return out
jobs=[('LED_B_A',('R18','2'),('D6','1')),('LED_R_A',('R16','2'),('D6','2')),('EN',('C11','1'),('R13','2')),('LED_G',('U4','7'),('R17','1'))]
plans=[]
for net,ka,kc in jobs:
    a=targets[ka];c=targets[kc];va,fa=escape(a,net)
    if net in ['LED_B_A','LED_R_A']:
        vc=(85.7,71.95 if net=='LED_B_A' else 73);fc=[]
    else:vc,fc=escape(c,net)
    path=route(va,vc,net)
    plans.append({'net':net,'front':[fa,fc],'back':path,'vias':[va,vc]})
    for x,y in [va,vc]:vias.append((x,y,.3,net))
    for layer,points in [('F.Cu',fa),('F.Cu',fc),('B.Cu',path)]:
        for p,q in zip(points,points[1:]):lines.append((np.array(p),np.array(q),.15 if layer=='B.Cu' else .1,net,layer))
    print(net,'routed via',va,vc,'with',len(path),'back nodes',flush=True)
(ROOT/'work/final_route_plan.json').write_text(json.dumps(plans,indent=2)+'\n')
stitches=[]
for key in [('U1','3'),('C3','2'),('D10','1'),('C11','2'),('D9','1'),('C9','2')]:
    v,path=escape(targets[key],'BGND');stitches.append({'ref':key,'via':v,'front':path})
    print('Ground stitch',key,v,flush=True)
(ROOT/'work/final_ground_plan.json').write_text(json.dumps(stitches,indent=2)+'\n')
