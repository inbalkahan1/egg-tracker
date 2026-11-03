import fs from 'node:fs/promises';
import path from 'node:path';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const [input,output]=process.argv.slice(2);
const d=JSON.parse(await fs.readFile(input,'utf8'));
const fps=d.video.fps,[gx,gy]=d.gravity_xy??[0,1];
if(!Number.isFinite(fps)||fps<=0||Math.abs(Math.hypot(gx,gy)-1)>1e-8)throw Error('Invalid frame rate or gravity vector');
const groups=new Map();
for(const [key,r] of Object.entries(d.records)){
 const split=key.lastIndexOf(':'),id=key.slice(0,split),frame=Number(key.slice(split+1));
 if(d.only_id!==null&&d.only_id!==undefined&&id!==d.only_id)continue;
 if(!groups.has(id))groups.set(id,new Map());groups.get(id).set(frame,r);
}
const selected=[...groups].filter(([id,rows])=>[...rows.values()].some(r=>r.egg&&r.status!=='rejected')&&(d.include_candidates||[...rows.values()].some(r=>r.status==='accepted')));
if(!selected.length)throw Error('No eligible tracks. Accept at least one frame or include unreviewed candidates.');
const wb=Workbook.create(),summary=wb.worksheets.add('Summary');
summary.getRange('A1:B8').values=[['EGG / OIL CENTER ANGLES',''],['Video',d.video.path],['Frame rate (fps)',fps],['Gravity X (image coordinates)',gx],['Gravity Y (image coordinates)',gy],['Angle convention','0 opposite gravity; positive clockwise in image; range -180 to +180'],['Source session',d.source_session],['Interpretation','Automatic IDs and oil circles require review. Missing/rejected angles are blank.']];
summary.getRange('A10:H10').values=[['Egg ID','First frame','Last frame','Span (s)','Egg observations','Oil observations','Accepted angles','Focus qualification']];
summary.getRange('A1:H1').format.fill='#173A49';summary.getRange('A1:H1').format.font.color='#FFFFFF';summary.getRange('A1:H1').format.font.bold=true;
summary.getRange('A:H').format.columnWidth=19;summary.getRange('A:A').format.columnWidth=32;summary.getRange('B:B').format.columnWidth=22;summary.getRange('H:H').format.columnWidth=28;
summary.getRange('A10:H10').format.fill='#DCEAF0';summary.getRange('A10:H10').format.wrapText=true;summary.getRange('A10:H10').format.rowHeight=36;summary.freezePanes.freezeRows(10);
const validations=[];let ix=0;
for(const [id,map] of selected){
 const observed=[...map].filter(([f,r])=>r.egg).map(([f])=>f),first=Math.min(...observed),last=Math.max(...observed);
 if(first<0||last>=d.video.frames)throw Error('Track frame outside video');
 const name=`Egg ${id}`.replace(/[\[\]:*?/\\]/g,'_').slice(0,25)+'_'+(++ix);
 const sh=wb.worksheets.add(name),rows=[];let eggN=0,oilN=0;
 for(let f=first;f<=last;f++){
  const r=map.get(f)??{status:'missing',focus:'unassessed'},e=r.egg??[null,null,null],o=r.oil??[null,null,null];
  if(r.egg)eggN++;if(r.oil)oilN++;
  rows.push([f,null,...e,...o,null,null,null,null,null,null,r.status??'unreviewed',r.focus??'unassessed',r.egg_source??'',r.oil_source??'']);
 }
 const end=7+rows.length;
 sh.getRange('A1').values=[[`EGG ${id} | per-frame center angles`]];
 sh.getRange('A2').values=[['All frames between first and last detected egg center are retained, including detection gaps.']];
 sh.getRange('A3').values=[['Signed angle is an automatic/edited proposal. Reviewed angle is populated only for accepted frames.']];
 sh.getRange('A4').values=[[`Gravity in image: ${d.gravity_label??'Down'}. Pixel origin upper-left; X right, Y down. Centers <1 pixel apart have no angle.`]];
 sh.getRange('A7:R7').values=[['Source frame','Clip time (s)','Egg X (px)','Egg Y (px)','Egg radius (px)','Oil X (px)','Oil Y (px)','Oil radius (px)','Delta X (px)','Delta Y (px)','Along zero axis','Clockwise component','Signed angle (deg)','Reviewed angle (deg)','Review status','Focus status','Egg source','Oil source']];
 sh.getRange(`A8:R${end}`).values=rows;
 const formulas=rows.map((row,i)=>{
  const r=i+8;
  return [`=IF(COUNT(C${r}:D${r},F${r}:G${r})=4,F${r}-C${r},"")`,`=IF(COUNT(C${r}:D${r},F${r}:G${r})=4,G${r}-D${r},"")`,`=IF(COUNT(I${r}:J${r})=2,-'Summary'!$B$4*I${r}-'Summary'!$B$5*J${r},"")`,`=IF(COUNT(I${r}:J${r})=2,'Summary'!$B$5*I${r}-'Summary'!$B$4*J${r},"")`,`=IF(AND(COUNT(I${r}:J${r})=2,SUMSQ(I${r}:J${r})>=1,O${r}<>"rejected"),IF(K${r}=0,90*SIGN(L${r}),DEGREES(ATAN(L${r}/K${r}))+IF(K${r}<0,IF(L${r}>=0,180,-180),0)),"")`,`=IF(AND(O${r}="accepted",ISNUMBER(M${r})),M${r},"")`];
 });
 sh.getRange(`B8:B${end}`).formulas=rows.map((r,i)=>[`=A${i+8}/'Summary'!$B$3`]);
 sh.getRange(`I8:N${end}`).formulas=formulas;
 sh.getRange('A:R').format.columnWidth=16;sh.getRange('O:R').format.columnWidth=20;
 sh.getRange(`B8:L${end}`).setNumberFormat('0.000');sh.getRange(`M8:N${end}`).setNumberFormat('+0.00;-0.00;0.00');
 sh.getRange('A1:R1').format.fill='#173A49';sh.getRange('A1:R1').format.font.color='#FFFFFF';sh.getRange('A1:R1').format.font.bold=true;sh.getRange('A1:R1').format.rowHeight=30;
 sh.getRange('A7:R7').format.fill='#DCEAF0';sh.getRange('A7:R7').format.wrapText=true;sh.getRange('A7:R7').format.font.bold=true;sh.getRange('A7:R7').format.rowHeight=38;
 sh.getRange(`N8:N${end}`).format.fill='#E5F2ED';sh.freezePanes.freezeRows(7);sh.showGridLines=true;
 summary.getRange(`A${10+ix}:H${10+ix}`).values=[[id,first,last,(last-first)/fps,eggN,oilN,null,'Not automatically assessed']];
 summary.getRange(`G${10+ix}`).formulas=[[`=COUNT('${name}'!N8:N${end})`]];
 validations.push({sh,rows,first,end,map,name});
}
wb.recalculate();
let validAngles=0;
for(const {sh,rows,first,end,map,name} of validations){
 const values=sh.getRange(`M8:N${end}`).values;
 for(let j=0;j<rows.length;j++){
  const r=map.get(first+j),e=r?.egg,o=r?.oil;let expected=null;
  if(e&&o&&r.status!=='rejected'){
   const dx=o[0]-e[0],dy=o[1]-e[1];
   if(Math.hypot(dx,dy)>=1)expected=Math.atan2(gy*dx-gx*dy,-gx*dx-gy*dy)*180/Math.PI;
  }
  const actual=values[j][0];
  if(expected!==null){if(typeof actual!=='number'||Math.abs(((actual-expected+540)%360)-180)>1e-7)throw Error('Signed angle validation failed '+name+' frame '+(first+j));validAngles++;}
  else if(actual!==''&&actual!==null)throw Error('Missing/rejected angle not blank');
  if(r?.status!=='accepted'&&values[j][1]!==''&&values[j][1]!==null)throw Error('Unreviewed angle in reviewed column');
 }
}
const preview=await wb.render({sheetName:validations[0].name,range:'A7:R14',scale:1,format:'png'});
await fs.writeFile(path.join(path.dirname(output),'excel_preview.png'),new Uint8Array(await preview.arrayBuffer()));
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
await fs.writeFile(path.join(path.dirname(output),'excel_validation.json'),JSON.stringify({sheets:validations.length,valid_candidate_angles:validAngles,all_angle_formulas_verified:true,output},null,2));
console.log(output);
