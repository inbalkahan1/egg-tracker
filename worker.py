from pathlib import Path
import argparse,json,shutil
import batch_track_all as batch
p=argparse.ArgumentParser();p.add_argument('--video',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--min-radius',type=float,default=15);p.add_argument('--max-radius',type=float,default=65);p.add_argument('--sensitivity',type=float,default=20);p.add_argument('--gravity',default='Down');p.add_argument('--limit',type=int)
a=p.parse_args()
if not 3<=a.min_radius<a.max_radius:raise ValueError('Minimum radius must be at least 3 and less than maximum radius.')
batch.MIN_RADIUS=a.min_radius;batch.MAX_RADIUS=a.max_radius;batch.SENSITIVITY=a.sensitivity
from tracker import signed_angle,GRAVITY
batch.angle=lambda e,o:signed_angle(e,o,GRAVITY[a.gravity])
batch.run(a.video,a.output,a.limit)
settings=dict(video=str(a.video.resolve()),min_egg_radius_px=a.min_radius,max_egg_radius_px=a.max_radius,sensitivity=a.sensitivity,gravity=a.gravity,gravity_xy={'Down':[0,1],'Up':[0,-1],'Left':[-1,0],'Right':[1,0]}[a.gravity])
(a.output/'project.json').write_text(json.dumps(settings,indent=2))
shutil.copy2(a.output/'session.json',a.output/'automatic_original.json')
