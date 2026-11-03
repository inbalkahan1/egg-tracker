"""Editable circle tracker. Automatic results are proposals, never reviewed truth."""
from pathlib import Path
import argparse,csv,json,math,hashlib,os
import cv2
import numpy as np
from PIL import Image,ImageTk
import tkinter as tk
from tkinter import ttk,messagebox

DEFAULT_VIDEO=r'F:\Inbal\example data 230826 1000\09-24-26\13-00-40.avi'
cv2.setNumThreads(1)

def angle(egg,oil):
    if egg is None or oil is None:return None
    dx,dy=oil[0]-egg[0],oil[1]-egg[1]
    return math.degrees(math.atan2(dx,-dy)) if math.hypot(dx,dy)>=1 else None

def gray(frame):return cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)

def circles(im,lo,hi,threshold=18):
    c=cv2.HoughCircles(cv2.GaussianBlur(im,(5,5),1),cv2.HOUGH_GRADIENT,1.1,max(8,lo),param1=55,param2=threshold,minRadius=max(2,int(lo)),maxRadius=max(3,int(hi)))
    return [] if c is None else c[0].astype(float).tolist()

def local_circle(im,prior,kind):
    x,y,r=prior;pad=max(14,r*(1.65 if kind=='egg' else 3))
    x0,y0=max(0,int(x-pad)),max(0,int(y-pad));x1,y1=min(im.shape[1],int(x+pad+1)),min(im.shape[0],int(y+pad+1))
    roi=im[y0:y1,x0:x1]
    if min(roi.shape,default=0)<10:return None
    candidates=circles(roi,r*.8,r*1.2,18 if kind=='egg' else 9)
    out=[]
    for a,b,rr in candidates:
        cx,cy=a+x0,b+y0;d=math.hypot(cx-x,cy-y)
        if d<=max(5,r*.55):out.append((d+2*abs(rr-r),[cx,cy,rr]))
    return min(out,key=lambda c:c[0])[1] if out else None

def detect_oil(im,egg,prior=None):
    x,y,r=egg
    x0,y0=max(0,int(x-r)),max(0,int(y-r));x1,y1=min(im.shape[1],int(x+r+1)),min(im.shape[0],int(y+r+1))
    roi=im[y0:y1,x0:x1]
    if min(roi.shape,default=0)<12:return None
    lo,hi=(max(2,prior[2]*.75),prior[2]*1.25) if prior else (max(2,r*.10),r*.40)
    candidates=circles(roi,lo,hi,9); scored=[]
    for a,b,rr in candidates:
        cx,cy=a+x0,b+y0
        if math.hypot(cx-x,cy-y)+rr>r*.98:continue
        if prior and math.hypot(cx-prior[0],cy-prior[1])>max(5,r*.30):continue
        ts=np.linspace(0,2*np.pi,48,endpoint=False)
        pts=np.array([[[cx+(rr+d)*math.cos(t),cy+(rr+d)*math.sin(t)] for t in ts] for d in [-1.5,1.5]],np.float32)
        vals=cv2.remap(im,pts[:,:,0],pts[:,:,1],cv2.INTER_LINEAR).astype(float)
        contrast=float(np.median(np.abs(vals[1]-vals[0])))
        if contrast<2:continue
        score=contrast-(.35*math.hypot(cx-prior[0],cy-prior[1]) if prior else 0)
        scored.append((score,[cx,cy,rr]))
    return max(scored,key=lambda c:c[0])[1] if scored else None

def track(prev,now,egg,oil):
    x,y,r=egg;p=int(r*1.3)+3
    x0,y0=max(0,int(x)-p),max(0,int(y)-p);x1,y1=min(prev.shape[1],int(x)+p),min(prev.shape[0],int(y)+p)
    template=prev[y0:y1,x0:x1]; margin=max(30,int(r))
    sx,sy=max(0,x0-margin),max(0,y0-margin);ex,ey=min(now.shape[1],x1+margin),min(now.shape[0],y1+margin)
    search=now[sy:ey,sx:ex]
    if min(template.shape)<12 or template.std()<2:return None,None,'weak template'
    result=cv2.matchTemplate(search,template,cv2.TM_CCOEFF_NORMED)
    _,score,_,loc=cv2.minMaxLoc(result)
    if score<.60:return None,None,'weak tracking match'
    dx,dy=loc[0]+sx-x0,loc[1]+sy-y0
    predicted=[x+dx,y+dy,r]
    found=local_circle(now,predicted,'egg')
    if found is None:return None,None,'egg boundary not found'
    prior=[oil[0]+dx,oil[1]+dy,oil[2]] if oil else None
    oc=detect_oil(now,found,prior)
    return found,oc,'automatic proposal' if oc else 'oil not detected'

class App:
    def __init__(self,root,video,out):
        self.root=root;self.video=str(Path(video).resolve());self.out=out;out.mkdir(parents=True,exist_ok=True)
        self.cap=cv2.VideoCapture(self.video)
        if not self.cap.isOpened():raise RuntimeError('Cannot open video: '+self.video)
        self.total=int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT));self.fps=self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps<=0:raise RuntimeError('Video has no valid FPS')
        stat=Path(video).stat();self.identity=dict(path=self.video,size=stat.st_size,mtime_ns=stat.st_mtime_ns,frames=self.total,fps=self.fps)
        self.file=out/'session.json';self.records={};self.idx=0;self.running=False;self.pending=None;self.candidates=[];self.frame=None
        if self.file.exists():
            saved=json.loads(self.file.read_text())
            if saved['video']!=self.identity:raise RuntimeError('Saved session belongs to a different or changed video. Choose another output folder.')
            self.records=saved['records'];self.idx=saved.get('last_frame',0)
        root.title('Egg and oil detector — review and correct');root.geometry('1230x880')
        bar=ttk.Frame(root);bar.pack(fill='x',padx=8,pady=4)
        ttk.Label(bar,text='Egg ID:').pack(side='left');self.id=tk.StringVar(value='1');ttk.Entry(bar,textvariable=self.id,width=5).pack(side='left')
        ttk.Button(bar,text='Load egg ID',command=self.change_id).pack(side='left')
        ttk.Label(bar,text='Frame:').pack(side='left',padx=8);self.framevar=tk.StringVar(value=str(self.idx));ttk.Entry(bar,textvariable=self.framevar,width=8).pack(side='left')
        ttk.Button(bar,text='Go',command=self.go).pack(side='left')
        for label,step in [('−10',-10),('Previous',-1),('Next',1),('+10',10)]:ttk.Button(bar,text=label,command=lambda s=step:self.navigate(s)).pack(side='left')
        ttk.Label(bar,text='End frame (blank = video end):').pack(side='left',padx=5);self.end=tk.StringVar();ttk.Entry(bar,textvariable=self.end,width=8).pack(side='left')
        bar2=ttk.Frame(root);bar2.pack(fill='x',padx=8)
        for label,fn in [('Find eggs',self.find),('Auto oil',self.auto_oil),('Track forward',self.start),('STOP',self.stop),('Accept frame',self.accept),('Reject frame',self.reject),('Save / export CSV',self.save)]:ttk.Button(bar2,text=label,command=fn).pack(side='left',padx=2)
        modes=ttk.Frame(root);modes.pack(fill='x',padx=8,pady=5)
        self.mode=tk.StringVar(value='select')
        for title,key in [('Select egg','select'),('Correct egg circle','egg'),('Correct oil circle','oil')]:ttk.Radiobutton(modes,text=title,variable=self.mode,value=key,command=self.reset_click).pack(side='left')
        self.focus=tk.StringVar(value='unassessed');ttk.Label(modes,text='Focus:').pack(side='left',padx=10)
        for label,key in [('Unassessed','unassessed'),('Clear','clear'),('Blurred','blurred')]:ttk.Radiobutton(modes,text=label,variable=self.focus,value=key,command=self.set_focus).pack(side='left')
        ttk.Button(modes,text='Clear oil',command=self.clear_oil).pack(side='left',padx=10)
        ttk.Label(root,text='Select: click an egg in the full image. Correct: click CENTER then EDGE in either image. Green = egg; orange = oil.').pack()
        self.canvas=tk.Canvas(root,width=1200,height=660,bg='#222');self.canvas.pack(padx=8,pady=5);self.canvas.bind('<Button-1>',self.click)
        self.status=tk.StringVar();ttk.Label(root,textvariable=self.status,wraplength=1190).pack(fill='x',padx=8)
        ttk.Label(root,text='0° opposite the chosen gravity direction; positive clockwise in the image. Automatic angles are proposals; accept only after review.').pack()
        root.protocol('WM_DELETE_WINDOW',self.close);self.load(self.idx)
    def key(self):return str(self.id.get()).strip()+':'+str(self.idx)
    def rec(self):return self.records.get(self.key(),dict(egg=None,oil=None,status='unreviewed',focus='unassessed',egg_source='',oil_source=''))
    def put(self,r):self.records[self.key()]=r
    def reset_click(self):self.pending=None
    def stop(self):self.running=False
    def change_id(self):self.stop();self.pending=None;self.candidates=[];self.load(self.idx)
    def go(self):
        try:self.load(int(self.framevar.get()))
        except ValueError:messagebox.showerror('Frame','Enter an integer frame number.')
    def navigate(self,step):self.load(self.idx+step)
    def load(self,idx,tracking=False):
        if not tracking:self.stop()
        if not 0<=idx<self.total:return
        if self.frame is None or idx!=self.idx+1:self.cap.set(cv2.CAP_PROP_POS_FRAMES,idx)
        ok,frame=self.cap.read()
        if not ok:raise RuntimeError(f'Cannot read frame {idx}')
        self.idx=idx;self.frame=frame;self.g=gray(frame);self.framevar.set(str(idx));self.pending=None;self.candidates=[]
        self.focus.set(self.rec().get('focus','unassessed'));self.draw()
    def draw(self):
        r=self.rec();h,w=self.frame.shape[:2];self.scale=min(740/w,550/h)
        full=cv2.resize(self.frame,(round(w*self.scale),round(h*self.scale)))
        def overlay(im,c,color,scale=1,offset=(0,0)):
            if c:
                p=(round((c[0]-offset[0])*scale),round((c[1]-offset[1])*scale));cv2.circle(im,p,round(c[2]*scale),color,1,cv2.LINE_AA);cv2.circle(im,p,2,color,-1)
        for c in self.candidates:overlay(full,c,(150,150,150),self.scale)
        for k,col in [('egg',(70,230,70)),('oil',(0,180,255))]:overlay(full,r.get(k),col,self.scale)
        c=r.get('egg');cx,cy=(c[:2] if c else (w/2,h/2));size=max(100,int(c[2]*4)) if c else 200
        self.zx,self.zy=round(cx-size/2),round(cy-size/2);self.zscale=440/size
        crop=np.zeros((size,size,3),np.uint8);sx,sy=max(0,self.zx),max(0,self.zy);ex,ey=min(w,self.zx+size),min(h,self.zy+size)
        if ex>sx and ey>sy:crop[sy-self.zy:ey-self.zy,sx-self.zx:ex-self.zx]=self.frame[sy:ey,sx:ex]
        zoom=cv2.resize(crop,(440,440),interpolation=cv2.INTER_NEAREST)
        for k,col in [('egg',(70,230,70)),('oil',(0,180,255))]:overlay(zoom,r.get(k),col,self.zscale,(self.zx,self.zy))
        self.photos=[ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(im,cv2.COLOR_BGR2RGB))) for im in [full,zoom]]
        self.canvas.delete('all');self.canvas.create_image(0,0,image=self.photos[0],anchor='nw');self.canvas.create_image(760,40,image=self.photos[1],anchor='nw')
        self.canvas.create_text(980,20,text='Zoom / circle correction',fill='white')
        a=angle(r.get('egg'),r.get('oil'));s='unavailable' if a is None else f'{a:+.2f}°'
        self.canvas.create_text(980,510,text=f'Angle: {s}\n{r["status"]}\nFocus: {r.get("focus","unassessed")}',fill='white',font=('Arial',15))
        self.status.set(f'Frame {self.idx}/{self.total-1} | {self.idx/self.fps:.3f} s | Egg {self.id.get()} | '+r.get('note','Click an egg to initialize.'))
    def click(self,event):
        self.stop()
        if event.x<740 and event.y<self.photos[0].height():x,y=event.x/self.scale,event.y/self.scale
        elif 760<=event.x<1200 and 40<=event.y<480:x,y=(event.x-760)/self.zscale+self.zx,(event.y-40)/self.zscale+self.zy
        else:return
        if not (0<=x<self.g.shape[1] and 0<=y<self.g.shape[0]):return
        mode=self.mode.get();r=dict(self.rec())
        if mode=='select':
            c=min(self.candidates,key=lambda c:math.hypot(c[0]-x,c[1]-y)) if self.candidates else None
            if c is None or math.hypot(c[0]-x,c[1]-y)>c[2]*1.5:
                pad=85;x0,y0=max(0,int(x)-pad),max(0,int(y)-pad)
                cs=circles(self.g[y0:int(y)+pad,x0:int(x)+pad],15,65)
                cs=[[a+x0,b+y0,rr] for a,b,rr in cs]
                c=min(cs,key=lambda c:math.hypot(c[0]-x,c[1]-y)) if cs else None
            if c is None or math.hypot(c[0]-x,c[1]-y)>65:
                self.status.set('No circle found. Choose Correct egg circle, then click center and edge.');return
            r.update(egg=c,oil=detect_oil(self.g,c),status='automatic',egg_source='automatic',oil_source='automatic',note='Review both circles before accepting.')
        elif self.pending is None:
            self.pending=(x,y,mode);self.status.set('Center selected. Now click the circumference.');return
        else:
            cx,cy,kind=self.pending;self.pending=None;radius=math.hypot(x-cx,y-cy)
            if radius<2:self.status.set('Circle must have radius of at least 2 pixels.');return
            if kind!=mode:return
            r[mode]=[cx,cy,radius];r[mode+'_source']='manual';r['status']='edited';r['note']='Manual edit saved; review and accept.'
            if mode=='egg' and r.get('oil') and math.dist(r['egg'][:2],r['oil'][:2])+r['oil'][2]>radius:r['oil']=None
        self.put(r);self.draw();self.save(quiet=True)
    def find(self):
        self.stop();small=cv2.resize(self.g,None,fx=.5,fy=.5)
        self.candidates=[[x*2,y*2,r*2] for x,y,r in circles(small,8,33,22)];self.draw();self.status.set(f'{len(self.candidates)} candidate circles. Click the target egg; false positives are possible.')
    def auto_oil(self):
        self.stop();r=dict(self.rec())
        if not r.get('egg'):return
        r.update(oil=detect_oil(self.g,r['egg'],r.get('oil')),oil_source='automatic',status='automatic',note='Automatic oil proposal; verify its identity.')
        self.put(r);self.draw();self.save(quiet=True)
    def clear_oil(self):
        self.stop();r=dict(self.rec());r.update(oil=None,oil_source='',status='edited');self.put(r);self.draw();self.save(quiet=True)
    def set_focus(self):
        self.stop();r=dict(self.rec());r['focus']=self.focus.get();self.put(r);self.draw();self.save(quiet=True)
    def accept(self):
        self.stop();r=dict(self.rec());e,o=r.get('egg'),r.get('oil')
        if angle(e,o) is None:messagebox.showinfo('Missing centers','Set both circles before accepting.');return
        if math.dist(e[:2],o[:2])+o[2]>e[2]*1.05:messagebox.showinfo('Check oil','The oil circle extends outside the egg. Correct it first.');return
        r['status']='accepted';self.put(r);self.draw();self.save(quiet=True)
    def reject(self):
        self.stop();r=dict(self.rec());r['status']='rejected';self.put(r);self.draw();self.save(quiet=True)
    def start(self):
        if not self.rec().get('egg'):messagebox.showinfo('Select egg','Select or draw an egg circle first.');return
        try:self.stopat=int(self.end.get()) if self.end.get().strip() else self.total-1
        except ValueError:messagebox.showerror('End frame','Enter an integer, or leave empty.');return
        if not self.idx<self.stopat<self.total:messagebox.showinfo('End frame','End frame must be later than the current frame and inside the video.');return
        self.running=True;self.root.after(1,self.tick)
    def tick(self):
        if not self.running:return
        if self.idx>=self.stopat:self.stop();self.save(quiet=True);return
        old=dict(self.rec());prev=self.g.copy();nextkey=self.id.get().strip()+':'+str(self.idx+1)
        if nextkey in self.records:
            self.stop();self.status.set('Stopped before an existing record. Navigate to it and review; saved edits are preserved.');return
        try:
            self.load(self.idx+1,tracking=True)
            e,o,note=track(prev,self.g,old['egg'],old.get('oil'))
            self.put(dict(egg=e,oil=o,status='automatic' if e else 'missing',focus='unassessed',egg_source='automatic',oil_source='automatic' if o else '',note=note))
            self.draw();self.save(quiet=True)
            if e is None:self.stop();self.status.set('Tracking paused: egg boundary uncertain. Correct this frame to continue.');return
            if o is None:self.stop();self.status.set('Tracking paused: oil uncertain. Correct oil before continuing.');return
            self.root.after(1,self.tick)
        except Exception as err:self.stop();messagebox.showerror('Tracking',str(err))
    def save(self,quiet=False):
        saved=dict(video=self.identity,last_frame=self.idx,records=self.records,angle_convention='0 opposite project gravity, positive clockwise in image')
        temp=self.file.with_suffix('.tmp');temp.write_text(json.dumps(saved,indent=2),encoding='utf-8');os.replace(temp,self.file)
        path=self.out/'measurements.csv';tmp=path.with_suffix('.tmp.csv')
        headers=['egg_id','source_frame','time_s','egg_x_px','egg_y_px','egg_radius_px','oil_x_px','oil_y_px','oil_radius_px','candidate_angle_deg','reviewed_angle_deg','review_status','focus','egg_source','oil_source']
        with tmp.open('w',newline='',encoding='utf-8') as f:
            wr=csv.writer(f);wr.writerow(headers)
            for key,r in sorted(self.records.items(),key=lambda p:(p[0].rsplit(':',1)[0],int(p[0].rsplit(':',1)[1]))):
                eid,fr=key.rsplit(':',1);a=angle(r.get('egg'),r.get('oil'))
                wr.writerow([eid,int(fr),int(fr)/self.fps]+(r.get('egg') or ['']*3)+(r.get('oil') or ['']*3)+[a if a is not None else '',a if a is not None and r['status']=='accepted' else '',r['status'],r.get('focus','unassessed'),r.get('egg_source',''),r.get('oil_source','')])
        try:os.replace(tmp,path)
        except PermissionError:
            if not quiet:messagebox.showinfo('CSV is open','Session saved. Close the CSV in Excel and export again.')
        if not quiet:self.status.set('Saved session and CSV: '+str(self.out))
    def close(self):self.stop();self.save(quiet=True);self.cap.release();self.root.destroy()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--video',default=DEFAULT_VIDEO);parser.add_argument('--output',type=Path);args=parser.parse_args()
    token=hashlib.sha256(str(Path(args.video).resolve()).encode()).hexdigest()[:8]
    out=args.output or Path(__file__).resolve().parent/'results'/(Path(args.video).stem+'_'+token)
    root=tk.Tk()
    try:App(root,args.video,out);root.mainloop()
    except Exception as err:messagebox.showerror('Detector error',str(err));raise
if __name__=='__main__':main()

