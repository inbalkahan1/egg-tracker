"""Full-video, multi-object circle proposals. Never marks automatic data reviewed."""
from pathlib import Path
from datetime import datetime
import argparse,json,csv,os,time,math,collections
import cv2,numpy as np
from egg_oil_detector import DEFAULT_VIDEO,circles,local_circle,detect_oil,angle
cv2.setNumThreads(1)

def atomic_json(path,obj):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,separators=(',',':')),encoding='utf-8');os.replace(tmp,path)

MIN_RADIUS=15.0;MAX_RADIUS=65.0;SENSITIVITY=20.0
def candidate_circles(g):
 small=cv2.resize(g,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
 rough=circles(small,MIN_RADIUS*.5,MAX_RADIUS*.5,SENSITIVITY);result=[]
 for x,y,r in rough:
  prior=[x*2,y*2,r*2];c=local_circle(g,prior,'egg')
  if c is None:continue
  x,y,r=c
  if not MIN_RADIUS<=r<=MAX_RADIUS:continue
  ts=np.linspace(0,2*np.pi,48,endpoint=False)
  pts=np.array([[[x+(r+d)*math.cos(t),y+(r+d)*math.sin(t)] for t in ts] for d in [-2,2]],np.float32)
  vals=cv2.remap(g,pts[:,:,0],pts[:,:,1],cv2.INTER_LINEAR).astype(float)
  edges=abs(vals[1]-vals[0]);contrast=float(np.median(edges));support=float(np.mean(edges>2))
  x0,y0=max(0,int(x-r)),max(0,int(y-r));roi=g[y0:min(g.shape[0],int(y+r+1)),x0:min(g.shape[1],int(x+r+1))]
  sharp=float(cv2.Laplacian(roi,cv2.CV_64F).var()) if roi.size else 0
  if contrast<2 or support<.45 or sharp<5:continue
  if any(math.dist(c[:2],old[0][:2])<.65*min(c[2],old[0][2]) for old in result):continue
  result.append((c,contrast,support,sharp))
 return result

def export(out,records,identity,last_frame):
 atomic_json(out/'session.json',dict(video=identity,last_frame=last_frame,records=records,angle_convention='0 up, positive right, negative left',automatic_batch=True))
 with (out/'measurements.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['egg_id','source_frame','time_s','egg_x_px','egg_y_px','egg_radius_px','oil_x_px','oil_y_px','oil_radius_px','candidate_angle_deg','reviewed_angle_deg','review_status','focus','egg_source','oil_source','note'])
  for key,r in records.items():
   eid,fr=key.rsplit(':',1);a=angle(r.get('egg'),r.get('oil'))
   w.writerow([eid,int(fr),int(fr)/identity['fps']]+(r.get('egg') or ['']*3)+(r.get('oil') or ['']*3)+[a if a is not None else '','',r['status'],r['focus'],r['egg_source'],r['oil_source'],r['note']])
 groups=collections.defaultdict(list)
 for key,r in records.items():
  eid,fr=key.rsplit(':',1);groups[eid].append((int(fr),r))
 summary=[]
 for eid,items in groups.items():
  found=[(f,r) for f,r in items if r['egg']]
  if not found:continue
  lo,hi=found[0][0],found[-1][0]
  summary.append(dict(egg_id=eid,first_frame=lo,last_frame=hi,span_s=(hi-lo)/identity['fps'],egg_detections=len(found),oil_detections=sum(r['oil'] is not None for _,r in found),missing_frames=sum(r['egg'] is None for _,r in items),ambiguous_frames=sum('ambiguous' in r['note'] for _,r in items),qualification='Unreviewed candidate; focus/identity not confirmed'))
 with (out/'track_summary.csv').open('w',newline='') as f:
  if summary:
   w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
 atomic_json(out/'track_summary.json',summary)
 return summary

def run(video,out,limit=None):
 out.mkdir(parents=True,exist_ok=False)
 cap=cv2.VideoCapture(str(video));assert cap.isOpened(),'Cannot open video'
 n=int(cap.get(cv2.CAP_PROP_FRAME_COUNT));fps=cap.get(cv2.CAP_PROP_FPS);stat=video.stat()
 identity=dict(path=str(video.resolve()),size=stat.st_size,mtime_ns=stat.st_mtime_ns,frames=n,fps=fps)
 nrun=min(n,limit) if limit else n
 records={};active={};nextid=1;started=time.time();counts=[]
 manifest=dict(video=identity,status='running',frames_processed=0,requested_frames=nrun,method='Half-resolution Hough detection on EVERY frame; native-resolution refinement; gated motion association; oil circle proposals',limitations=['Candidate IDs can fragment or switch at overlap.','Oil identity requires manual review; another internal structure may be selected.','No interpolated centers; no automatic focus qualification.','Original reviewed session is separate and unchanged.'])
 atomic_json(out/'run_status.json',manifest)
 for frame_idx in range(nrun):
  if (out/'STOP').exists():nrun=frame_idx;break
  ok,frame=cap.read()
  if not ok:raise RuntimeError(f'Video decode failed at {frame_idx}')
  g=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY);found=candidate_circles(g);counts.append(len(found))
  pairs=[]
  for eid,tr in active.items():
   gap=frame_idx-tr['last_frame'];pred=np.array(tr['egg'][:2])+tr['velocity']*gap
   for j,(c,_,_,_) in enumerate(found):
    dist=float(np.linalg.norm(pred-np.array(c[:2])));rd=abs(c[2]-tr['egg'][2])/tr['egg'][2]
    if dist<=min(100,35+10*gap) and rd<=.35:pairs.append((dist+25*rd,eid,j))
  assigned={};used=set();taken=set()
  for score,eid,j in sorted(pairs):
   if eid in used or j in taken:continue
   ambiguous=any((oe==eid or oj==j) and (oe,oj)!=(eid,j) and abs(other-score)<8 for other,oe,oj in pairs)
   assigned[j]=(eid,ambiguous);used.add(eid);taken.add(j)
  for j,(c,contrast,support,sharp) in enumerate(found):
   if j in assigned:eid,ambiguous=assigned[j]
   else:eid=str(nextid);nextid+=1;ambiguous=False
   old=active.get(eid);prior=None;velocity=np.zeros(2)
   if old:
    delta=np.array(c[:2])-np.array(old['egg'][:2]);velocity=.5*old['velocity']+.5*delta/(frame_idx-old['last_frame'])
    if old['oil'] is not None:prior=[old['oil'][0]+delta[0],old['oil'][1]+delta[1],old['oil'][2]]
   oil=detect_oil(g,c,prior)
   # Reacquisition is explicitly flagged: it can be a different internal structure.
   reacquired=False
   if oil is None and prior is not None:oil=detect_oil(g,c);reacquired=oil is not None
   note='automatic proposal'
   if ambiguous:note+='; ambiguous identity association'
   if reacquired:note+='; oil reacquired - verify identity'
   if oil is None:note+='; oil not detected'
   if c[0]-c[2]<0 or c[1]-c[2]<0 or c[0]+c[2]>=g.shape[1] or c[1]+c[2]>=g.shape[0]:note+='; edge clipped'
   records[f'{eid}:{frame_idx}']=dict(egg=c,oil=oil,status='automatic',focus='unassessed',egg_source='automatic',oil_source='automatic' if oil else '',note=note,edge_contrast=contrast,boundary_support=support,sharpness=sharp)
   active[eid]=dict(egg=c,oil=oil,velocity=velocity,last_frame=frame_idx)
  for eid in list(active):
   if active[eid]['last_frame']==frame_idx:continue
   gap=frame_idx-active[eid]['last_frame']
   records[f'{eid}:{frame_idx}']=dict(egg=None,oil=None,status='missing',focus='unassessed',egg_source='',oil_source='',note='No matched circle; centers not interpolated')
   if gap>=5:del active[eid]
  if frame_idx%25==0 or frame_idx==nrun-1:
   manifest.update(frames_processed=frame_idx+1,elapsed_s=round(time.time()-started,1),candidate_tracks=nextid-1,records=len(records))
   atomic_json(out/'run_status.json',manifest)
   print(json.dumps(manifest|{'video':str(video),'limitations':None}),flush=True)
  if frame_idx%1000==0:atomic_json(out/'session.checkpoint.json',dict(video=identity,last_frame=frame_idx,records=records,automatic_batch=True))
 cap.release()
 summary=export(out,records,identity,0)
 manifest.update(status='complete' if nrun==manifest['requested_frames'] else 'stopped',frames_processed=nrun,elapsed_s=round(time.time()-started,1),candidate_tracks=len(summary),egg_detections=sum(c['egg_detections'] for c in summary),oil_detections=sum(c['oil_detections'] for c in summary),tracks_spanning_one_second=sum(c['span_s']>=1 for c in summary))
 atomic_json(out/'run_status.json',manifest)
 print(json.dumps(manifest),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--video',type=Path,default=Path(DEFAULT_VIDEO));p.add_argument('--output',type=Path,required=True);p.add_argument('--limit',type=int);a=p.parse_args();run(a.video,a.output,a.limit)


