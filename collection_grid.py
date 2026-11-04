"""Contact-sheet grid of every collection sample: one annotated crop per egg, excluded samples outlined in red."""
from pathlib import Path,PureWindowsPath
import json,math,sys
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
CELL=240;GAP=8;LABEL=52;MARGIN=8;HEADER=72;CROP_SCALE=1.5
BG=(24,32,42);BORDER=(150,170,185);EXCLUDED=(235,90,90);TEXT=(245,245,245);SUBTEXT=(185,192,200)

def font(size,bold=False):
    for name in (['DejaVuSans-Bold.ttf','arialbd.ttf'] if bold else ['DejaVuSans.ttf','arial.ttf']):
        try:return ImageFont.truetype(name,size)
        except OSError:pass
    return ImageFont.load_default()

def local(path,folder):
    """Annotated image path; Windows paths from the other PC are resolved inside this collection folder."""
    p=Path(path)
    if p.exists():return p
    parts=PureWindowsPath(path).parts
    return folder/Path(*parts[parts.index('images'):]) if 'images' in parts else p

def crop(sample,folder):
    im=Image.open(local(sample['annotated_image'],folder)).convert('RGB')
    x,y,r=sample['egg'];half=max(8,r*CROP_SCALE)
    box=tuple(round(v) for v in (x-half,y-half,x+half,y+half))
    tile=Image.new('RGB',(box[2]-box[0],box[3]-box[1]),(0,0,0))
    inside=(max(0,box[0]),max(0,box[1]),min(im.width,box[2]),min(im.height,box[3]))
    if inside[0]<inside[2] and inside[1]<inside[3]:tile.paste(im.crop(inside),(inside[0]-box[0],inside[1]-box[1]))
    return tile.resize((CELL,CELL),Image.LANCZOS)

def build(folder,out=None):
    folder=Path(folder);samples=sorted(json.loads((folder/'collection.json').read_text())['samples'],key=lambda s:s['sample_id'])
    cols=math.ceil(math.sqrt(len(samples)));rows=math.ceil(len(samples)/cols)
    width=MARGIN*2+cols*CELL+(cols-1)*GAP;height=HEADER+rows*(CELL+LABEL)+(rows-1)*GAP+MARGIN
    sheet=Image.new('RGB',(width,height),BG);draw=ImageDraw.Draw(sheet)
    excluded=sum(s['excluded'] for s in samples)
    draw.text((MARGIN,10),f'Egg and oil-globule collection | {len(samples)} samples ({len(samples)-excluded} included, {excluded} excluded) | {cols} x {rows}',fill=TEXT,font=font(26,True))
    draw.text((MARGIN,46),'Green: egg | Orange: oil globule | White arrow: 0 deg (opposite gravity) | Red border: excluded sample | Crops enlarged individually; not a shared size scale',fill=SUBTEXT,font=font(16))
    big,small=font(16),font(13)
    for i,s in enumerate(samples):
        x=MARGIN+(i%cols)*(CELL+GAP);y=HEADER+(i//cols)*(CELL+LABEL+GAP)
        sheet.paste(crop(s,folder),(x,y))
        colour=EXCLUDED if s['excluded'] else BORDER
        draw.rectangle((x-1,y-1,x+CELL,y+CELL),outline=colour,width=3 if s['excluded'] else 1)
        draw.text((x+4,y+CELL+5),f"#{s['sample_id']:03d}  Egg {s['egg_id']}  {s['angle_deg']:+.1f}°",fill=EXCLUDED if s['excluded'] else TEXT,font=big)
        draw.text((x+4,y+CELL+26),f"{PureWindowsPath(s['video']).stem} | f{s['frame']}"+(' | EXCLUDED' if s['excluded'] else ''),fill=EXCLUDED if s['excluded'] else SUBTEXT,font=small)
    out=Path(out) if out else folder/'organized_images'/f'all_eggs_circles_grid_{cols}x{rows}.png'
    out.parent.mkdir(parents=True,exist_ok=True);sheet.save(out);return out

if __name__=='__main__':print(build(sys.argv[1] if len(sys.argv)>1 else ROOT/'angle_collection',sys.argv[2] if len(sys.argv)>2 else None))
