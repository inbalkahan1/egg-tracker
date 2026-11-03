"""One randomly sampled reviewed frame per tracked egg, across videos."""
from pathlib import Path
import json,math,hashlib,random,os,sys,subprocess,copy
from datetime import datetime,timezone
from collections import defaultdict
import cv2
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk
ROOT=Path(__file__).resolve().parent
DEFAULT=ROOT/'angle_collection'
BUNDLED=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
def atomic(path,data):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2),encoding='utf-8');os.replace(temp,path)
def angle(e,o,g):
    dx,dy=o[0]-e[0],o[1]-e[1];gx,gy=g
    return math.degrees(math.atan2(gy*dx-gx*dy,-gx*dx-gy*dy))
def valid(r):
    if r.get('status') not in ('edited','accepted') or r.get('focus')=='blurred':return False
    e,o=r.get('egg'),r.get('oil')
    if not e or not o or len(e)!=3 or len(o)!=3:return False
    if not all(math.isfinite(x) for x in e+o) or min(e[2],o[2])<=0:return False
    return math.dist(e[:2],o[:2])>=1 and math.dist(e[:2],o[:2])+o[2]<=e[2]*1.05
def frame_image(sample):
    video=Path(sample['video']);st=video.stat()
    if st.st_size!=sample['video_size'] or st.st_mtime_ns!=sample['video_mtime_ns']:raise ValueError('Video changed since tracking: '+str(video))
    cap=cv2.VideoCapture(str(video))
    try:
        if not cap.isOpened():raise ValueError('Cannot open '+str(video))
        cap.set(cv2.CAP_PROP_POS_FRAMES,sample['frame']);ok,im=cap.read()
        if not ok:raise ValueError('Cannot read frame '+str(sample['frame']))
        return im
    finally:cap.release()
def annotated(im,sample):
    im=im.copy();e,o=sample['egg'],sample['oil'];gx,gy=sample['gravity']
    for c,color in [(e,(70,230,70)),(o,(0,165,255))]:
        p=tuple(round(v) for v in c[:2]);cv2.circle(im,p,round(c[2]),color,2,cv2.LINE_AA);cv2.circle(im,p,2,color,-1)
    p=tuple(round(v) for v in e[:2]);cv2.line(im,p,tuple(round(v) for v in o[:2]),(0,165,255),1,cv2.LINE_AA)
    cv2.arrowedLine(im,p,(round(e[0]-gx*e[2]),round(e[1]-gy*e[2])),(255,255,255),1,cv2.LINE_AA)
    label=f"Sample {sample['sample_id']} | egg {sample['egg_id']} | frame {sample['frame']} | {sample['status']} | {sample['angle_deg']:+.2f} deg"
    cv2.putText(im,label,(12,30),cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,0),4,cv2.LINE_AA)
    cv2.putText(im,label,(12,30),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),1,cv2.LINE_AA)
    return im
def save_png(path,im):
    ok,b=cv2.imencode('.png',im)
    if not ok:raise ValueError('Could not encode PNG')
    path.write_bytes(b.tobytes())
class Collection:
    def __init__(self,folder=DEFAULT):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
        self.file=self.folder/'collection.json'
        self.data=json.loads(self.file.read_text()) if self.file.exists() else dict(seed=random.SystemRandom().randrange(2**32),target=100,samples=[],created=datetime.now(timezone.utc).isoformat())
        self.loaded=self.file.read_text() if self.file.exists() else None
    def save(self):
        lock=self.folder/'collection.lock'
        try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:raise RuntimeError('Another collection window is saving. Retry shortly.')
        try:
            current=self.file.read_text() if self.file.exists() else None
            if current!=self.loaded:raise RuntimeError('Collection changed in another window. Close and reopen this window before editing.')
            atomic(self.file,self.data);self.loaded=self.file.read_text()
        finally:os.close(fd);lock.unlink()

    def import_project(self,project,include_unassessed=True):
        project=Path(project);d=json.loads((project/'session.json').read_text());v=d['video']
        settings=json.loads((project/'project.json').read_text()) if (project/'project.json').exists() else {}
        g=settings.get('gravity_xy',[0,1])
        if len(g)!=2 or abs(math.hypot(*g)-1)>1e-8:raise ValueError('Invalid gravity vector')
        # Video content fingerprint avoids duplicates when the same video is copied/renamed.
        path=Path(v['path']);st=path.stat()
        if st.st_size!=v['size'] or st.st_mtime_ns!=v['mtime_ns']:raise ValueError('Source video has changed: '+str(path))
        h=hashlib.sha256();h.update(str(st.st_size).encode())
        with path.open('rb') as f:
            for off in sorted(set([0,max(0,st.st_size//2-32768),max(0,st.st_size-65536)])):
                f.seek(off);h.update(f.read(65536))
        vid=h.hexdigest()[:20];groups=defaultdict(list);trajectories=defaultdict(dict)
        for key,r in d['records'].items():
            eid,frame=key.rsplit(':',1);frame=int(frame)
            if r.get('egg'):trajectories[eid][frame]=r['egg']
            if valid(r) and (include_unassessed or r.get('focus')=='clear'):groups[eid].append((frame,r))
        added=0;skipped=0
        for eid,choices in sorted(groups.items()):
            # Stable session key avoids accidentally merging unrelated IDs from a new analysis.
            source_key=hashlib.sha256((str(project.resolve()).lower()+'|'+eid).encode()).hexdigest()
            existing=next((s for s in self.data['samples'] if s['source_key']==source_key),None)
            if existing:skipped+=1;continue
            # Match other analyses/fragments only at a shared frame and almost identical egg center/radius.
            duplicates=[]
            for s in self.data['samples']:
                if s['video_key']!=vid:continue
                c=trajectories[eid].get(s['frame'])
                if c and math.dist(c[:2],s['egg'][:2])<.35*min(c[2],s['egg'][2]) and abs(c[2]-s['egg'][2])<.4*s['egg'][2]:
                    duplicates.append(s['sample_id'])
            rng=random.Random(str(self.data['seed'])+source_key)
            frame,r=rng.choice(sorted(choices))
            sid=max([s['sample_id'] for s in self.data['samples']]+[0])+1
            sample=dict(sample_id=sid,source_key=source_key,video_key=vid,video=str(path),video_size=v['size'],video_mtime_ns=v['mtime_ns'],project=str(project),egg_id=eid,frame=frame,fps=v['fps'],egg=r['egg'],oil=r['oil'],gravity=g,status=r['status'],focus=r.get('focus','unassessed'),eligible_frames=len(choices),angle_deg=angle(r['egg'],r['oil'],g),identity_confirmed=False,excluded=bool(duplicates),exclusion_reason=('Possible duplicate of sample(s) '+','.join(map(str,duplicates))) if duplicates else '',imported=datetime.now(timezone.utc).isoformat())
            if not math.isfinite(v['fps']) or v['fps']<=0:raise ValueError('Invalid FPS')
            raw=frame_image(sample);dest=self.folder/'images'/f'egg_sample_{sid:03d}';dest.mkdir(parents=True,exist_ok=True)
            sample['raw_image']=str(dest/'raw.png');sample['annotated_image']=str(dest/'circles.png')
            save_png(Path(sample['raw_image']),raw);save_png(Path(sample['annotated_image']),annotated(raw,sample))
            self.data['samples'].append(sample);self.save();added+=1
        return added,skipped
    def export(self):
        self.save()
        result=subprocess.run([str(BUNDLED),str(ROOT/'collection_excel.py'),str(self.folder)],capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise RuntimeError('Collection and images saved, but Excel export failed. Close the workbook in Excel and retry.\n'+result.stderr[-1200:])
        return self.folder/'egg_angle_collection.xlsx'
class App:
    def __init__(self,root,folder=DEFAULT,project=None):
        self.root=root;self.c=Collection(folder);self.project=project;self.photo=None
        root.title('Egg angle collection — one frame per egg');root.geometry('1180x840')
        self.include=tk.BooleanVar(value=True);bar=ttk.Frame(root);bar.pack(fill='x',padx=8,pady=6)
        for label,fn in [('Choose saved project',self.add),('Open video tracker',self.tracker),('Change collection folder',self.folder),('Save Excel',self.export)]:
            ttk.Button(bar,text=label,command=lambda fn=fn:self.guard(fn)).pack(side='left',padx=4)
        ttk.Checkbutton(root,text='Include edited/accepted frames with unassessed focus (blurred frames are always excluded)',variable=self.include).pack(anchor='w',padx=12)
        self.info=tk.StringVar();ttk.Label(root,textvariable=self.info).pack(fill='x',padx=12)
        self.tree=ttk.Treeview(root,columns=('video','egg','frame','angle','focus','identity','state'),show='headings',height=9)
        for name in self.tree['columns']:self.tree.heading(name,text=name.title());self.tree.column(name,width=130)
        self.tree.pack(fill='x',padx=8);self.tree.bind('<<TreeviewSelect>>',lambda e:self.guard(self.preview))
        actions=ttk.Frame(root);actions.pack(fill='x',padx=8,pady=5)
        for index,(label,fn) in enumerate([('Confirm focused + distinct egg',self.confirm),('Exclude duplicate / poor frame',self.exclude),('Restore selected sample',self.restore),('Correct in tracker',self.review),('Reload corrected frame',self.reload_frame),('Reject frame; sample another',self.resample)]):
            ttk.Button(actions,text=label,command=lambda fn=fn:self.guard(fn)).grid(row=index//3,column=index%3,padx=4,pady=2,sticky='w')
        ttk.Label(root,text='Images: original crop on left; circles on right. Initial sampling is random, independent of angle. Exclude duplicates before analysis.').pack()
        self.canvas=tk.Canvas(root,width=1100,height=420,bg='#222');self.canvas.pack(fill='both',expand=True,padx=8)
        self.note=tk.StringVar();ttk.Label(root,textvariable=self.note,wraplength=1120).pack(fill='x',padx=10)
        self.refresh()
        if project:root.after(100,lambda:self.guard(lambda:self.import_path(project)))
    def guard(self,fn):
        try:fn()
        except Exception as e:messagebox.showerror('Collection',str(e))
    def refresh(self):
        sel=self.tree.selection();self.tree.delete(*self.tree.get_children())
        for s in self.c.data['samples']:
            self.tree.insert('',tk.END,iid=str(s['sample_id']),values=(Path(s['video']).name,s['egg_id'],s['frame'],f"{s['angle_deg']:+.2f}",s['focus'],'confirmed' if s['identity_confirmed'] else 'check',s['exclusion_reason'] if s['excluded'] else 'included'))
        active=[s for s in self.c.data['samples'] if not s['excluded']]
        confirmed=[s for s in active if s['focus']=='clear' and s['identity_confirmed']]
        self.info.set(f'{len(active)} included samples | {len(confirmed)} focus + identity confirmed / target {self.c.data["target"]} | {self.c.folder}')
        if sel and self.tree.exists(sel[0]):self.tree.selection_set(sel[0])
    def selected(self):
        selection=self.tree.selection()
        if not selection:raise ValueError('Select a sample first.')
        return next(s for s in self.c.data['samples'] if str(s['sample_id'])==selection[0])
    def preview(self):
        s=self.selected();im=cv2.imdecode(__import__('numpy').fromfile(s['raw_image'],dtype='uint8'),cv2.IMREAD_COLOR)
        if im is None:raise ValueError('Saved image is missing.')
        x,y,r=s['egg'];pad=max(50,r*2)
        x0,y0=max(0,int(x-pad)),max(0,int(y-pad));x1,y1=min(im.shape[1],int(x+pad)),min(im.shape[0],int(y+pad))
        marked=annotated(im,s);panels=[]
        for pic in [im,marked]:
            crop=pic[y0:y1,x0:x1];pil=Image.fromarray(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB));pil.thumbnail((510,400));panels.append(pil)
        out=Image.new('RGB',(1040,410),'#222222')
        for i,pil in enumerate(panels):out.paste(pil,(i*520,0))
        self.photo=ImageTk.PhotoImage(out);self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photo,anchor='nw')
        self.note.set(f"Sample {s['sample_id']} | {s['video']} | selected randomly from {s['eligible_frames']} eligible frames. {s['exclusion_reason']}")
    def import_path(self,p):
        a,b=self.c.import_project(p,self.include.get());self.refresh()
        out=self.c.export();messagebox.showinfo('Imported',f'{a} samples added; {b} existing samples retained.\n{out}')
    def add(self):
        p=filedialog.askopenfilename(title='Choose saved tracker session.json',filetypes=[('Tracker project','session.json')])
        if p:self.import_path(Path(p).parent)
    def tracker(self):subprocess.Popen([sys.executable,str(ROOT/'tracker.py')],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def folder(self):
        p=filedialog.askdirectory(title='Choose a collection folder (keep using the same one across videos)')
        if p:self.c=Collection(p);self.refresh()
    def export(self):messagebox.showinfo('Excel saved',str(self.c.export()))
    def confirm(self):
        s=self.selected();s['focus']='clear';s['identity_confirmed']=True;s['excluded']=False;s['exclusion_reason']='';s['collection_reviewed_at']=datetime.now(timezone.utc).isoformat();self.c.save();self.refresh();self.c.export()
    def exclude(self):
        s=self.selected();s['excluded']=True;s['exclusion_reason']='Excluded by reviewer';self.c.save();self.refresh();self.c.export()
    def restore(self):
        s=self.selected();s['excluded']=False;s['exclusion_reason']='';s['identity_confirmed']=False;self.c.save();self.refresh();self.c.export()
    def update_sample(self,s,frame,r,pool_count):
        if not valid(r):raise ValueError('This frame is not eligible: it must be edited/accepted, not blurred, with both valid circles.')
        if not self.include.get() and r.get('focus')!='clear':raise ValueError('Mark this frame Clear in the tracker first.')
        s.setdefault('selection_history',[]).append({k:copy.deepcopy(s[k]) for k in ['frame','egg','oil','status','focus','angle_deg']})
        s.update(frame=frame,egg=r['egg'],oil=r['oil'],status=r['status'],focus=r.get('focus','unassessed'),identity_confirmed=False,eligible_frames=pool_count)
        s['angle_deg']=angle(s['egg'],s['oil'],s['gravity'])
        # New files preserve previous images as an audit trail.
        dest=Path(s['raw_image']).parent;version=len(s['selection_history'])
        s['raw_image']=str(dest/f'raw_revision_{version}.png');s['annotated_image']=str(dest/f'circles_revision_{version}.png')
        raw=frame_image(s);save_png(Path(s['raw_image']),raw);save_png(Path(s['annotated_image']),annotated(raw,s))
        self.c.save();self.refresh();self.preview();self.c.export()
    def reload_frame(self):
        s=self.selected();d=json.loads((Path(s['project'])/'session.json').read_text())
        r=d['records'].get(f"{s['egg_id']}:{s['frame']}")
        if r is None:raise ValueError('Source frame was removed or its track ID changed.')
        self.update_sample(s,s['frame'],r,s['eligible_frames'])
    def resample(self):
        s=self.selected();d=json.loads((Path(s['project'])/'session.json').read_text())
        rejected=set(s.get('rejected_frames',[]));rejected.add(s['frame'])
        candidates=[]
        for key,r in d['records'].items():
            eid,f=key.rsplit(':',1);f=int(f)
            if eid==s['egg_id'] and f not in rejected and valid(r) and (self.include.get() or r.get('focus')=='clear'):candidates.append((f,r))
        if not candidates:raise ValueError('No other eligible frame. Review more frames in the tracker, or exclude this sample.')
        frame,r=random.Random(str(self.c.data['seed'])+s['source_key']+str(len(rejected))).choice(sorted(candidates))
        s['rejected_frames']=sorted(rejected);self.update_sample(s,frame,r,len(candidates))
    def review(self):
        s=self.selected()
        subprocess.Popen([sys.executable,str(ROOT/'tracker.py'),'--review',s['project']],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        messagebox.showinfo('Source project',f"Select egg {s['egg_id']} and go to frame {s['frame']} in the tracker. Collection images are a saved snapshot; they do not update automatically.")
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--project',type=Path);parser.add_argument('--folder',type=Path,default=DEFAULT);parser.add_argument('--scan',type=Path);a=parser.parse_args()
    if a.scan:
        c=Collection(a.folder);report=[]
        for p in a.scan.rglob('session.json'):
            if 'validation' in p.parts or 'angle_collection' in p.parts:continue
            try:report.append([str(p),c.import_project(p.parent)])
            except Exception as e:report.append([str(p),str(e)])
        c.save();print(json.dumps(report));print(c.export())
    else:
        root=tk.Tk();app=App(root,a.folder,a.project);root.mainloop()

