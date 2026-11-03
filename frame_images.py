"""Export reviewed frame images without changing tracking measurements."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import json, math, cv2

def export_frame_images(project, minimum=50):
    project=Path(project)
    data=json.loads((project/'session.json').read_text(encoding='utf-8'))
    settings=json.loads((project/'project.json').read_text()) if (project/'project.json').exists() else {}
    gx,gy=settings.get('gravity_xy',[0,1])
    groups=defaultdict(dict)
    for key,r in data['records'].items():
        eid,f=key.rsplit(':',1)
        if r.get('status') in ('edited','accepted') and r.get('egg'):
            if not eid.isdigit():raise ValueError('Egg IDs must be numeric.')
            groups[eid][int(f)]=r
    groups={eid:rows for eid,rows in groups.items() if len(rows)>=minimum}
    if not groups:raise ValueError(f'No egg has at least {minimum} edited or accepted frames with an egg circle.')
    video=Path(data['video']['path']);stat=video.stat()
    if stat.st_size!=data['video']['size'] or stat.st_mtime_ns!=data['video']['mtime_ns']:
        raise ValueError('The source video has changed since this project was saved.')
    cap=cv2.VideoCapture(str(video))
    if not cap.isOpened():raise ValueError('Cannot open source video.')
    output=project/('reviewed_frame_images_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir()
    manifest={'status':'incomplete','minimum_frames':minimum,'source_video':str(video),'gravity_xy':[gx,gy],'eggs':{},'images_saved':0}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    by_frame=defaultdict(list)
    for eid,rows in groups.items():
        (output/f'egg_{eid}').mkdir()
        manifest['eggs'][eid]={'frame_count':len(rows),'frames':sorted(rows)}
        for f,r in rows.items():by_frame[f].append((eid,r))
    previous=-2
    try:
        for f,items in sorted(by_frame.items()):
            if f!=previous+1:cap.set(cv2.CAP_PROP_POS_FRAMES,f)
            ok,frame=cap.read()
            if not ok:raise RuntimeError(f'Unable to read source frame {f}; partial export: {output}')
            previous=f
            for eid,r in items:
                im=frame.copy();e=r['egg'];o=r.get('oil')
                for c,color in ((e,(60,230,60)),(o,(0,165,255))):
                    if c:
                        center=tuple(round(v) for v in c[:2]);cv2.circle(im,center,round(c[2]),color,2,cv2.LINE_AA);cv2.circle(im,center,2,color,-1)
                a=None
                if o:
                    dx,dy=o[0]-e[0],o[1]-e[1]
                    if math.hypot(dx,dy)>=1:a=math.degrees(math.atan2(gy*dx-gx*dy,-gx*dx-gy*dy))
                    cv2.line(im,tuple(round(v) for v in e[:2]),tuple(round(v) for v in o[:2]),(0,165,255),1,cv2.LINE_AA)
                cv2.arrowedLine(im,tuple(round(v) for v in e[:2]),(round(e[0]-gx*e[2]),round(e[1]-gy*e[2])),(255,255,255),1,cv2.LINE_AA,tipLength=.15)
                angle='unavailable' if a is None else f'{a:+.2f} deg'
                label=f'Egg {eid} | frame {f} | {f/data["video"]["fps"]:.3f} s | {r["status"]} | angle {angle}'
                scale=max(.3,min(1.2,(im.shape[1]-16)/max(1,cv2.getTextSize(label,cv2.FONT_HERSHEY_SIMPLEX,1,2)[0][0])))
                cv2.putText(im,label,(8,25),cv2.FONT_HERSHEY_SIMPLEX,scale,(0,0,0),4,cv2.LINE_AA)
                cv2.putText(im,label,(8,25),cv2.FONT_HERSHEY_SIMPLEX,scale,(255,255,255),1,cv2.LINE_AA)
                target=output/f'egg_{eid}'/f'frame_{f:06d}_{r["status"]}.png'
                ok,encoded=cv2.imencode('.png',im)
                if not ok:raise RuntimeError('PNG encoding failed')
                target.write_bytes(encoded.tobytes());manifest['images_saved']+=1
        manifest['status']='complete'
    finally:
        cap.release();(output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return output
