from pathlib import Path
import json,math,sys,subprocess,threading,queue,copy
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from datetime import datetime
import egg_oil_detector as core
from review_all_eggs import BatchReview
ROOT=Path(__file__).resolve().parent
NODE=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
GRAVITY={'Down':(0,1),'Up':(0,-1),'Left':(-1,0),'Right':(1,0)}
def get_settings(project):
 p=project/'project.json'
 return json.loads(p.read_text()) if p.exists() else {'gravity':'Down','gravity_xy':[0,1]}
def signed_angle(egg,oil,gravity):
 if egg is None or oil is None:return None
 dx,dy=oil[0]-egg[0],oil[1]-egg[1]
 if math.hypot(dx,dy)<1:return None
 gx,gy=gravity
 return math.degrees(math.atan2(gy*dx-gx*dy,-gx*dx-gy*dy))
def export_excel(project,include_candidates=True,only_id=None):
 if not NODE.is_file():raise RuntimeError('Excel export runtime not found: '+str(NODE))
 d=json.loads((project/'session.json').read_text());s=get_settings(project);d['gravity_xy']=s['gravity_xy'];d['gravity_label']=s['gravity'];d['include_candidates']=include_candidates;d['only_id']=only_id;d['source_session']=str(project/'session.json')
 if only_id is not None and not str(only_id).isdigit():raise ValueError('Egg ID must be a number.')
 target=project/('egg_angles.xlsx' if only_id is None else f'egg_{only_id}_angles.xlsx')
 snapshot=project/'excel_export_snapshot.json';snapshot.write_text(json.dumps(d),encoding='utf-8')
 result=subprocess.run([str(NODE),'--max-old-space-size=8000',str(ROOT/'export_excel.mjs'),str(snapshot),str(target)],capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError(result.stderr[-2500:] or result.stdout[-2500:])
 return target
def open_collection(project=None):
 args=[sys.executable,str(ROOT/'collection.py')]
 if project:args+=['--project',str(project)]
 subprocess.Popen(args,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
class Review(BatchReview):
 def __init__(self,root,project):
  self.gravity=get_settings(project)['gravity_xy'];self.project=project;self.exporting=False;self.messages=queue.Queue()
  core.angle=lambda e,o:signed_angle(e,o,self.gravity)
  d=json.loads((project/'session.json').read_text());super().__init__(root,d['video']['path'],project)
  root.title('Egg & Oil Tracker | review, correct, export');self.canvas.configure(height=560)
  bar=ttk.Frame(root);bar.pack(fill='x',padx=8,pady=6)
  self.export_all=tk.BooleanVar(value=True);ttk.Checkbutton(bar,text='Include unreviewed candidate tracks in Excel',variable=self.export_all).pack(side='left')
  ttk.Button(bar,text='Export ALL eggs to Excel',command=self.export).pack(side='left',padx=5)
  ttk.Button(bar,text='Export selected egg',command=lambda:self.export(self.id.get())).pack(side='left',padx=5)
  ttk.Button(bar,text='Re-track next 50 automatic frames',command=self.refine).pack(side='left',padx=5)
  imagebar=ttk.Frame(root);imagebar.pack(fill='x',padx=8,pady=3)
  ttk.Button(imagebar,text='Export frame images (50+ edited / accepted)',command=self.export_images).pack(side='left')
  ttk.Button(imagebar,text='Collect one frame per egg',command=self.collect_samples).pack(side='left',padx=6)
  root.after(200,self.poll_export)
 def collect_samples(self):
  if self.exporting:return
  self.stop();self.save(quiet=True);open_collection(self.project)
 def export_images(self):
  if self.exporting:return
  self.stop();self.save(quiet=True);self.exporting=True;self.status.set('Exporting edited / accepted frame images...')
  def task():
   try:
    from frame_images import export_frame_images
    self.messages.put(('ok',str(export_frame_images(self.project))))
   except Exception as e:self.messages.put(('error',str(e)))
  threading.Thread(target=task,daemon=True).start()
 def close(self):
  if self.exporting:messagebox.showinfo('Please wait','An export is still being saved.');return
  super().close()
 def draw(self):
  super().draw()
  c=self.rec().get('egg')
  if c:
   x=760+(c[0]-self.zx)*self.zscale;y=40+(c[1]-self.zy)*self.zscale
   gx,gy=self.gravity;length=min(160,c[2]*self.zscale+20)
   self.canvas.create_line(x,y,x-gx*length,y-gy*length,fill='white',dash=(3,3),arrow=tk.LAST)
 def export(self,only=None):
  if self.exporting:return
  self.stop();self.save(quiet=True);self.exporting=True;include=self.export_all.get();self.status.set('Creating Excel workbook...')
  def task():
   try:self.messages.put(('ok',str(export_excel(self.project,include,only))))
   except Exception as e:self.messages.put(('error',str(e)))
  threading.Thread(target=task,daemon=True).start()
 def poll_export(self):
  try:
   kind,msg=self.messages.get_nowait();self.exporting=False;self.status.set(msg)
   if kind=='error':messagebox.showerror('Export',msg)
   else:messagebox.showinfo('Export saved',msg)
  except queue.Empty:pass
  self.root.after(200,self.poll_export)
 def refine(self):
  if not self.rec().get('egg') or not self.rec().get('oil'):messagebox.showinfo('Refine','Correct both circles on the current frame first.');return
  self.stop();self.refine_end=min(self.idx+50,self.total-1);self.refine_changes={};self.undo_stack.append(self.refine_changes);self.running=True;self.root.after(1,self.refine_tick)
 def refine_tick(self):
  try:self._refine_tick()
  except Exception as e:
   self.stop();self.save(quiet=True);messagebox.showerror("Re-tracking",str(e))
 def _refine_tick(self):
  if not self.running or self.idx>=self.refine_end:self.stop();self.save(quiet=True);return
  key=f'{self.id.get()}:{self.idx+1}';existing=self.records.get(key)
  if existing and (existing['status'] in ['accepted','edited','rejected'] or existing.get('egg_source')=='manual' or existing.get('oil_source')=='manual'):
   self.stop();self.status.set('Stopped before a manual edit/reviewed frame; it was preserved.');self.save(quiet=True);return
  old=self.rec();prev=self.g.copy();self.load(self.idx+1,tracking=True)
  e,o,note=core.track(prev,self.g,old['egg'],old.get('oil'))
  self.refine_changes[key]=copy.deepcopy(existing)
  self.records[key]=dict(egg=e,oil=o,status='automatic' if e else 'missing',focus=(existing or {}).get('focus','unassessed'),egg_source='automatic',oil_source='automatic' if o else '',note='Re-tracked from corrected seed: '+note)
  self.frame_index[self.idx].add(self.id.get());self.track_index[self.id.get()].add(self.idx);self.draw()
  if e is None or o is None:self.stop();self.save(quiet=True);self.status.set('Re-tracking paused at uncertain boundary; correct this frame.');return
  self.root.after(1,self.refine_tick)
class Launcher:
 def __init__(self,root):
  self.root=root;self.process=None;self.review_process=None;self.project=None;self.log=None;self.messages=queue.Queue();self.busy=False
  root.title('Egg & Oil Tracker | choose video');root.geometry('800x450')
  self.video=tk.StringVar();self.project_root=tk.StringVar(value=str(ROOT/'projects'))
  self.lo=tk.StringVar(value='15');self.hi=tk.StringVar(value='65');self.sensitivity=tk.StringVar(value='20');self.gravity=tk.StringVar(value='Down');self.auto_excel=tk.BooleanVar(value=True)
  panel=ttk.Frame(root,padding=16);panel.pack(fill='both',expand=True)
  ttk.Label(panel,text='AVI video').grid(row=0,column=0,sticky='w');ttk.Entry(panel,textvariable=self.video,width=70).grid(row=1,column=0,columnspan=3,sticky='ew');ttk.Button(panel,text='Browse...',command=self.browse).grid(row=1,column=3)
  ttk.Label(panel,text='Projects folder').grid(row=2,column=0,sticky='w');ttk.Entry(panel,textvariable=self.project_root,width=70).grid(row=3,column=0,columnspan=3,sticky='ew');ttk.Button(panel,text='Choose...',command=self.folder).grid(row=3,column=3)
  row=ttk.Frame(panel);row.grid(row=4,column=0,columnspan=4,pady=12,sticky='w')
  for label,var in [('Min egg radius (pixels)',self.lo),('Max radius',self.hi),('Detection threshold',self.sensitivity)]:ttk.Label(row,text=label).pack(side='left');ttk.Entry(row,textvariable=var,width=6).pack(side='left',padx=5)
  ttk.Label(row,text='Gravity').pack(side='left');ttk.Combobox(row,textvariable=self.gravity,values=list(GRAVITY),state='readonly',width=7).pack(side='left')
  ttk.Checkbutton(panel,text='Create initial Excel workbook after tracking (unreviewed estimates)',variable=self.auto_excel).grid(row=5,column=0,columnspan=4,sticky='w')
  actions=ttk.Frame(panel);actions.grid(row=6,column=0,columnspan=4,pady=12,sticky='w')
  for label,fn in [('Start automatic tracking',self.start),('Stop and save',self.stop),('Open saved project',self.open_project),('Review current project',self.review)]:ttk.Button(actions,text=label,command=fn).pack(side='left',padx=3)
  self.progress=ttk.Progressbar(panel,length=730,maximum=100);self.progress.grid(row=7,column=0,columnspan=4)
  self.status=tk.StringVar(value='Choose a video. Automatic circles and IDs need review; original video is not modified.')
  ttk.Label(panel,textvariable=self.status,wraplength=730).grid(row=8,column=0,columnspan=4,pady=10,sticky='w')
  ttk.Button(panel,text='Open shared egg-angle collection',command=open_collection).grid(row=9,column=0,columnspan=4,sticky='w')
  ttk.Button(panel,text='Open chosen AVI for manual review',command=self.manual_project).grid(row=9,column=2,columnspan=2,sticky='e')
  root.after(500,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)
 def manual_project(self):
  if self.busy:return
  try:
   video=Path(self.video.get())
   if not video.is_file():raise ValueError('Browse to an AVI first.')
   cap=core.cv2.VideoCapture(str(video))
   try:
    if not cap.isOpened():raise ValueError('Cannot open video.')
    fps=cap.get(core.cv2.CAP_PROP_FPS);frames=int(cap.get(core.cv2.CAP_PROP_FRAME_COUNT))
   finally:cap.release()
   if fps<=0 or frames<1:raise ValueError('Invalid video frame rate or length.')
   dest=Path(self.project_root.get());dest.mkdir(parents=True,exist_ok=True)
   self.project=dest/(video.stem+'_manual_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));self.project.mkdir()
   st=video.stat()
   d=dict(video=dict(path=str(video.resolve()),size=st.st_size,mtime_ns=st.st_mtime_ns,frames=frames,fps=fps),last_frame=0,records={})
   (self.project/'session.json').write_text(json.dumps(d))
   (self.project/'project.json').write_text(json.dumps(dict(gravity=self.gravity.get(),gravity_xy=GRAVITY[self.gravity.get()])))
   self.status.set('Manual project created. Use New ID for each distinct egg, draw both circles, mark Clear and Accept frame.')
   self.review()
  except Exception as e:messagebox.showerror('Manual project',str(e))
 def browse(self):
  value=filedialog.askopenfilename(filetypes=[('AVI video','*.avi'),('Video files','*.mp4 *.mov *.mkv'),('All files','*.*')])
  if value:self.video.set(value)
 def folder(self):
  value=filedialog.askdirectory()
  if value:self.project_root.set(value)
 def start(self):
  if self.busy:return
  try:
   video=Path(self.video.get());lo,hi,threshold=float(self.lo.get()),float(self.hi.get()),float(self.sensitivity.get())
   if not video.is_file():raise ValueError('Choose an existing AVI file.')
   if not 3<=lo<hi or threshold<=0:raise ValueError('Check radius bounds and detection threshold.')
   dest=Path(self.project_root.get());dest.mkdir(parents=True,exist_ok=True)
   self.project=dest/(video.stem+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
   self.log=(dest/(self.project.name+'.log')).open('w',encoding='utf-8')
   args=[sys.executable,str(ROOT/'worker.py'),'--video',str(video.resolve()),'--output',str(self.project),'--min-radius',str(lo),'--max-radius',str(hi),'--sensitivity',str(threshold),'--gravity',self.gravity.get()]
   self.do_excel=self.auto_excel.get();self.process=subprocess.Popen(args,stdout=self.log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.busy=True;self.progress['value']=0;self.status.set('Scanning every frame; results saved in '+str(self.project))
  except Exception as e:messagebox.showerror('Start tracking',str(e))
 def stop(self):
  if self.process and self.process.poll() is None and self.project.exists():(self.project/'STOP').touch();self.status.set('Stopping after the current frame and saving...')
 def open_project(self):
  if self.busy:return
  value=filedialog.askopenfilename(title='Choose a saved session.json',filetypes=[('Tracker session','session.json')])
  if value:self.project=Path(value).parent;self.review()
 def review(self):
  if self.busy:messagebox.showinfo('Please wait','Wait for tracking/export to finish, or Stop and save.');return
  if not self.project or not (self.project/'session.json').exists():return
  if self.review_process and self.review_process.poll() is None:messagebox.showinfo('Review window','The review window is already open.');return
  self.review_process=subprocess.Popen([sys.executable,str(ROOT/'tracker.py'),'--review',str(self.project)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 def poll(self):
  if self.process:
   status=self.project/'run_status.json'
   if status.exists():
    try:
     d=json.loads(status.read_text());done=d['frames_processed'];total=d['requested_frames'];self.progress['value']=100*done/max(1,total);self.status.set(f'Processed {done:,} / {total:,} frames. Candidate tracks require review.')
    except (ValueError,OSError):pass
   code=self.process.poll()
   if code is not None:
    self.log.close();self.process=None
    if code:self.busy=False;self.status.set('Tracking failed; see the project log.');messagebox.showerror('Tracking failed','See '+str(self.project)+'.log')
    elif self.do_excel:
     self.status.set('Tracking saved. Creating the initial Excel workbook...')
     project=self.project
     def task():
      try:self.messages.put(('ok',str(export_excel(project))))
      except Exception as e:self.messages.put(('error',str(e)))
     threading.Thread(target=task,daemon=True).start()
    else:self.busy=False;self.status.set('Saved. Click Review current project to correct detections.');self.review()
  try:
   kind,msg=self.messages.get_nowait();self.busy=False;self.status.set(('Excel saved: ' if kind=='ok' else 'Excel export failed: ')+msg)
   if kind=='error':messagebox.showerror('Export',msg)
   self.review()
  except queue.Empty:pass
  self.root.after(500,self.poll)
 def close(self):
  if self.busy:self.stop();self.status.set('Please wait for saving/export to finish before closing.');return
  self.root.destroy()
if __name__=='__main__':
 root=tk.Tk()
 if len(sys.argv)>2 and sys.argv[1]=='--review':Review(root,Path(sys.argv[2]))
 else:Launcher(root)
 root.mainloop()
