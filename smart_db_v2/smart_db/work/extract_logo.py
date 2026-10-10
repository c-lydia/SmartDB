"""Convert the proposal cover's logo into monochrome vector silkscreen geometry."""
import cv2,json
from pathlib import Path
root=Path('/tmp/smartdb_review/compact');im=cv2.imread(str(root/'proposal_cover.png'))
# Cover rendered at 1400px tall. Bounding box includes shield and wordmark, excludes micro-tagline.
h,w=im.shape[:2];roi=im[486:724,349:674]
b,g,r=cv2.split(roi)
mask=(((r.astype(float)+g.astype(float)+b.astype(float))/3<155)&((b<180)|(b.astype(int)-r.astype(int)>35))).astype('uint8')*255
mask=cv2.resize(mask,(280,205),interpolation=cv2.INTER_AREA);mask=(mask>125).astype('uint8')
# Merge equal horizontal runs vertically into rectangles. This preserves the logo's counters/holes.
active={};rects=[]
for y,row in enumerate(mask):
 runs=[];start=None
 for x,v in enumerate(list(row)+[0]):
  if v and start is None:start=x
  if not v and start is not None:runs.append((start,x));start=None
 new={}
 for run in runs:new[run]=active.pop(run,y)
 for (a,z),yy in active.items():rects.append([a,yy,z,y])
 active=new
for (a,z),yy in active.items():rects.append([a,yy,z,len(mask)])
(root/'logo_rects.json').write_text(json.dumps(rects))
svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 280 205"><title>SmartDB logo extracted from proposal cover</title>']
for x,y,xx,yy in rects:svg.append(f'<rect x="{x}" y="{y}" width="{xx-x}" height="{yy-y}"/>')
svg.append('</svg>');(root/'smartdb-logo-monochrome.svg').write_text('\n'.join(svg))
print('Logo converted to',len(rects),'vector rectangles; source image',w,h)
