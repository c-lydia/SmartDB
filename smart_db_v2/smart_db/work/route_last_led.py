"""Find a 0.3 mm outer-layer route across existing routing channels."""
from pathlib import Path
import heapq,json,math
ROOT=Path(__file__).resolve().parent.parent
source=(ROOT/'work/finish_route_plan.py').read_text().split('jobs=')[0]
exec(source)
net='LED_G';a=targets['U4','7'];c=targets['R17','1'];va,fa=escape(a,net);vc,fc=escape(c,net)
grids=[route(None,None,net,l,grid_only=True,track_width=.3) for l in ['F.Cu','B.Cu']]
vg=route(None,None,net,grid_only=True,via_grid=True)
def idx(p):return round((p[0]-X0)/STEP),round((p[1]-Y0)/STEP)
start=(1,*idx(va));end=(1,*idx(vc));heap=[(0,start)];dist={start:0};prev={};seen=set()
assert not grids[start[0]][start[1:]] and not grids[end[0]][end[1:]]
while heap:
    _,p=heapq.heappop(heap)
    if p in seen:continue
    seen.add(p)
    if p==end:break
    l,x,y=p
    adjacent=[]
    for dx,dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)]:
        nx,ny=x+dx,y+dy
        if not(0<=nx<len(xs) and 0<=ny<len(ys)) or grids[l][nx,ny]:continue
        if dx and dy and (grids[l][nx,y] or grids[l][x,ny]):continue
        adjacent.append(((l,nx,ny),math.sqrt(2) if dx and dy else 1))
    if not vg[x,y]:adjacent.append(((1-l,x,y),60))
    for q,cost in adjacent:
        nd=dist[p]+cost
        if nd<dist.get(q,float('inf')):
            dist[q]=nd;prev[q]=p;heapq.heappush(heap,(nd+math.hypot(q[1]-end[1],q[2]-end[2]),q))
else:raise RuntimeError('No two-layer path')
points=[end]
while points[-1]!=start:points.append(prev[points[-1]])
points.reverse();groups=[];layer=points[0][0];group=[];extra=[]
for l,x,y in points:
    p=[round(X0+x*STEP,4),round(Y0+y*STEP,4)]
    if l!=layer:
        groups.append((layer,group));extra.append(p);group=[p];layer=l
    else:group.append(p)
groups.append((layer,group))
groups[0][1][0]=list(va);groups[-1][1][-1]=list(vc)
paths=[{'layer':'F.Cu','points':fa,'width':.2},{'layer':'F.Cu','points':fc,'width':.2}]
for layer,ps in groups:
    def clear(a,c):
        samples=np.linspace(a,c,max(2,math.ceil(math.dist(a,c)/.02)))
        ix=np.rint((samples[:,0]-X0)/STEP).astype(int);iy=np.rint((samples[:,1]-Y0)/STEP).astype(int)
        return not grids[layer][ix,iy].any()
    simple=[ps[0]];i=0
    while i<len(ps)-1:
        a=ps[i]
        for j in range(len(ps)-1,i,-1):
            c=ps[j];dx=c[0]-a[0];dy=c[1]-a[1];d=min(abs(dx),abs(dy));sx=1 if dx>=0 else -1;sy=1 if dy>=0 else -1
            bends=[[a[0]+sx*d,a[1]+sy*d],[c[0]-sx*d,c[1]-sy*d],[a[0],c[1]],[c[0],a[1]]]
            bend=next((v for v in bends if clear(a,v) and clear(v,c)),None)
            if bend is not None:
                if math.dist(a,bend)>.001:simple.append(bend)
                if math.dist(simple[-1],c)>.001:simple.append(c)
                i=j;break
        else:raise RuntimeError('Cannot simplify final LED path')
    paths.append({'layer':['F.Cu','B.Cu'][layer],'points':simple,'width':.3})
plan=[{'net':net,'paths':paths,'vias':[list(va),list(vc),*extra]}]
(ROOT/'work/final_route_plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print('LED route:',len(seen),'search nodes,',len(extra)+2,'vias,',sum(len(p['points'])-1 for p in paths),'segments',flush=True)
