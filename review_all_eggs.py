"""Manual review of full-video candidate trajectories, using the existing circle editor."""
from pathlib import Path
import argparse,copy,json,tkinter as tk
from tkinter import ttk,messagebox
from collections import defaultdict
from egg_oil_detector import App,DEFAULT_VIDEO

class BatchReview(App):
 def __init__(self,root,video,out):
  self.frame_index=defaultdict(set);self.track_index=defaultdict(set);self.undo_stack=[];self.ready=False
  super().__init__(root,video,out)
  root.title('All eggs — review automatic trajectories');root.geometry('1240x980');self.canvas.configure(height=580)
  extra=ttk.Frame(root);extra.pack(fill='x',padx=8,pady=6)
  ttk.Label(extra,text='Tracks (longest first):').pack(side='left')
  self.min_count=tk.StringVar(value='1');self.choice=tk.StringVar();self.picker=ttk.Combobox(extra,textvariable=self.choice,state='readonly',width=48);self.picker.pack(side='left');self.picker.bind('<<ComboboxSelected>>',self.choose_track)
  for title,fn in [('First',self.first),('Last',self.last),('New ID',self.new_id),('Undo edit',self.undo),('Reject track',self.reject_track)]:ttk.Button(extra,text=title,command=fn).pack(side='left',padx=2)
  bar=ttk.Frame(root);bar.pack(fill='x',padx=8,pady=4)
  ttk.Label(bar,text='Min detections:').pack(side='left');ttk.Entry(bar,textvariable=self.min_count,width=5).pack(side='left');ttk.Button(bar,text='Filter list',command=self.refresh_picker).pack(side='left')
  ttk.Button(bar,text='Split track here',command=self.split).pack(side='left')
  ttk.Label(bar,text='Merge selected into ID:').pack(side='left',padx=5);self.merge_target=tk.StringVar();ttk.Entry(bar,textvariable=self.merge_target,width=8).pack(side='left')
  ttk.Button(bar,text='Merge non-overlapping tracks',command=self.merge).pack(side='left')
  self.show_others=tk.BooleanVar(value=True);ttk.Checkbutton(bar,text='Show other tracks',variable=self.show_others,command=self.draw).pack(side='left',padx=8)
  ttk.Label(root,text='Every circle is an unreviewed proposal. Missing circles stay blank. Split/merge repair IDs; Accept frame validates measurements only.').pack()
  self.ready=True;self.reindex();self.refresh_picker()
  if self.track_index:self.id.set(self.ordered[0]);self.first()
 def reindex(self):
  self.frame_index=defaultdict(set);self.track_index=defaultdict(set)
  for key in self.records:
   eid,f=key.rsplit(':',1);f=int(f);self.frame_index[f].add(eid);self.track_index[eid].add(f)
 def refresh_picker(self):
  self.ordered=sorted(self.track_index,key=lambda e:(-sum(bool(self.records[f'{e}:{f}'].get('egg')) for f in self.track_index[e]),int(e)))
  try:minimum=max(1,int(self.min_count.get()))
  except ValueError:minimum=10
  self.ordered=[eid for eid in self.ordered if eid==self.id.get() or sum(bool(self.records[f'{eid}:{f}'].get('egg')) for f in self.track_index[eid])>=minimum]
  self.labels=[]
  for eid in self.ordered:
   frames=sorted(self.track_index[eid]);obs=[f for f in frames if self.records[f'{eid}:{f}'].get('egg')]
   oil=sum(bool(self.records[f'{eid}:{f}'].get('oil')) for f in frames)
   self.labels.append(f'{eid} | frames {min(obs or frames)}-{max(obs or frames)} | egg {len(obs)}, oil {oil}')
  self.picker['values']=self.labels
  if self.id.get() in self.ordered:self.choice.set(self.labels[self.ordered.index(self.id.get())])
 def choose_track(self,event=None):
  self.stop();self.id.set(self.ordered[self.picker.current()]);self.first()
 def change_id(self):
  if not self.id.get().strip().isdigit():
   self.id.set(self.ordered[0] if getattr(self,"ordered",[]) else "1");messagebox.showerror("Egg ID","Use a numeric egg ID.");return
  super().change_id()
  if self.ready:self.refresh_picker()
 def first(self):
  fs=self.track_index.get(self.id.get(),set())
  if fs:self.load(min(fs));self.refresh_picker()
 def last(self):
  fs=self.track_index.get(self.id.get(),set())
  if fs:self.load(max(fs));self.refresh_picker()
 def new_id(self):
  self.stop();self.id.set(str(max([int(i) for i in self.track_index]+[0])+1));self.pending=None;self.draw();self.status.set('New track: select or draw its egg circle on this frame.')
 def put(self,r):
  key=self.key()
  self.undo_stack.append({key:copy.deepcopy(self.records.get(key))})
  if len(self.undo_stack)>100:self.undo_stack.pop(0)
  super().put(r)
  eid,f=key.rsplit(':',1);self.frame_index[int(f)].add(eid);self.track_index[eid].add(int(f))
 def undo(self):
  self.stop()
  if not self.undo_stack:return
  for k,v in self.undo_stack.pop().items():
   if v is None:self.records.pop(k,None)
   else:self.records[k]=v
  self.reindex();self.refresh_picker();self.draw();self.save(quiet=True)
 def reject_track(self):
  self.stop();eid=self.id.get();keys=[f'{eid}:{f}' for f in self.track_index.get(eid,[])]
  self.undo_stack.append({k:copy.deepcopy(self.records[k]) for k in keys})
  for k in keys:self.records[k]['status']='rejected'
  self.draw();self.save(quiet=True)
 def split(self):
  self.stop();eid=self.id.get();frames=self.track_index.get(eid,set())
  if not frames or self.idx<=min(frames) or self.idx>max(frames):messagebox.showinfo('Split','Choose a frame inside the track, after its first frame.');return
  new=str(max(map(int,self.track_index))+1);changes={}
  for f in list(frames):
   if f<self.idx:continue
   oldkey=f'{eid}:{f}';newkey=f'{new}:{f}';changes[oldkey]=copy.deepcopy(self.records[oldkey]);changes[newkey]=None
   self.records[newkey]=self.records.pop(oldkey)
  self.undo_stack.append(changes);self.id.set(new);self.reindex();self.refresh_picker();self.draw();self.save(quiet=True)
 def merge(self):
  self.stop();source=self.id.get();target=self.merge_target.get().strip()
  if source==target or target not in self.track_index:messagebox.showinfo('Merge','Choose a different existing target ID.');return
  overlap=self.track_index[source]&self.track_index[target]
  if any(self.records[f'{source}:{f}'].get('egg') and self.records[f'{target}:{f}'].get('egg') for f in overlap):messagebox.showinfo('Merge','Both IDs contain egg measurements on the same frame. Split the conflicting portion first.');return
  changes={}
  for f in list(self.track_index[source]):
   sk,tk=f'{source}:{f}',f'{target}:{f}';changes[sk]=copy.deepcopy(self.records[sk]);changes[tk]=copy.deepcopy(self.records.get(tk))
   if tk not in self.records or not self.records[tk].get('egg'):self.records[tk]=self.records[sk]
   del self.records[sk]
  self.undo_stack.append(changes);self.id.set(target);self.reindex();self.refresh_picker();self.draw();self.save(quiet=True)
 def draw(self):
  super().draw()
  if not self.ready:return
  if self.show_others.get():
   for eid in self.frame_index.get(self.idx,[]):
    if eid==self.id.get():continue
    c=self.records[f'{eid}:{self.idx}'].get('egg')
    if c:
     x,y,r=[v*self.scale for v in c];self.canvas.create_oval(x-r,y-r,x+r,y+r,outline='#AAAAAA');self.canvas.create_text(x,y-r-7,text=eid,fill='#FFFFFF')
  points=[]
  for f in range(max(0,self.idx-40),self.idx+1):
   c=self.records.get(f'{self.id.get()}:{f}',{}).get('egg')
   if c:
    points.extend([c[0]*self.scale,c[1]*self.scale])
   else:
    if len(points)>=4:self.canvas.create_line(*points,fill='#00CC88')
    points=[]
  if len(points)>=4:self.canvas.create_line(*points,fill='#00CC88')
 def click(self,event):
  # In selection mode, clicking an existing circle selects its ID, not a new annotation.
  if self.ready and self.mode.get()=='select' and event.x<740 and event.y<self.photos[0].height():
   x,y=event.x/self.scale,event.y/self.scale;near=[]
   for eid in self.frame_index.get(self.idx,[]):
    c=self.records[f'{eid}:{self.idx}'].get('egg')
    if c:
     dist=((x-c[0])**2+(y-c[1])**2)**.5
     if dist<c[2]*1.5:near.append((dist,eid))
   if near:
    self.stop();self.id.set(min(near)[1]);self.pending=None;self.focus.set(self.rec().get('focus','unassessed'));self.refresh_picker();self.draw();return
  super().click(event)
  if self.ready:self.refresh_picker()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'results/all_eggs_20261025');a=p.parse_args()
 if not (a.output/'session.json').exists():raise SystemExit('Batch session is not complete yet.')
 saved=json.loads((a.output/'session.json').read_text());root=tk.Tk();app=BatchReview(root,saved['video']['path'],a.output);root.mainloop()


