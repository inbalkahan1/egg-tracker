"""Spreadsheet export for the egg collection. Bundled artifact runtime unavailable; openpyxl fallback."""
from pathlib import Path
import json,sys,math
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.chart import BarChart,Reference
from openpyxl.worksheet.table import Table,TableStyleInfo
def export(folder):
    folder=Path(folder);d=json.loads((folder/'collection.json').read_text());samples=d['samples']
    wb=Workbook();summary=wb.active;summary.title='Summary';sh=wb.create_sheet('Egg samples')
    headers=['Sample ID','Video','Egg track ID','Source frame','Clip time (s)','Egg X (px)','Egg Y (px)','Egg radius (px)','Oil X (px)','Oil Y (px)','Oil radius (px)','Signed angle (deg)','Source review status','Focus status','Distinct egg confirmed','Included','Eligible source frames','Gravity X','Gravity Y','Source project','Raw frame','Annotated frame','Exclusion reason']
    sh.append(headers)
    for s in samples:
        sh.append([s['sample_id'],s['video'],s['egg_id'],s['frame'],s['frame']/s['fps'],*s['egg'],*s['oil'],s['angle_deg'],s['status'],s['focus'],'yes' if s['identity_confirmed'] else 'no','no' if s['excluded'] else 'yes',s['eligible_frames'],*s['gravity'],s['project'],s['raw_image'],s['annotated_image'],s['exclusion_reason']])
        for col,key in [(21,'raw_image'),(22,'annotated_image')]:
            sh.cell(sh.max_row,col).hyperlink=Path(s[key]).as_uri();sh.cell(sh.max_row,col).style='Hyperlink'
    if samples:
        for row in sh.iter_rows(min_row=2):
            if row[0].row%2==0:
                for cell in row:cell.fill=PatternFill('solid',fgColor='F1F5F8')
    sh.freeze_panes='F2';sh.auto_filter.ref=sh.dimensions
    for col in range(1,24):
        from openpyxl.utils import get_column_letter
        sh.column_dimensions[get_column_letter(col)].width=18 if col<20 else 45
    sh.column_dimensions['B'].width=48;sh.column_dimensions['M'].width=23;sh.column_dimensions['O'].width=23
    for row in sh.iter_rows(min_row=2):
        for c in row[4:12]:c.number_format='0.000'
    for c in sh[1]:c.fill=PatternFill('solid',fgColor='24465C');c.font=Font(name='Arial',size=10,bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True,vertical='center')
    sh.row_dimensions[1].height=34
    active=[s for s in samples if not s['excluded']]
    confirmed=[s for s in active if s['identity_confirmed'] and s['focus']=='clear']
    summary.append(['Egg oil-angle collection'])
    for row in [
      ['Target distinct focused eggs',d.get('target',100)],['Included candidate samples',len(active)],
      ['Focus + identity confirmed',len(confirmed)],['Remaining to confirmed target',max(0,d.get('target',100)-len(confirmed))],
      ['Excluded / possible duplicates',len(samples)-len(active)],
      ['Sampling','One frame chosen uniformly from eligible edited/accepted frames per source track. Selection is retained on reimport.'],
      ['Eligibility','Both valid circles; oil inside egg; blurred frames excluded. Unassessed focus included by user request.'],
      ['Angle convention','0 opposite gravity; clockwise positive. For downward gravity: up 0, right +90, left -90.'],
      ['Interpretation','Track IDs are not guaranteed unique biological eggs. Confirm focus and identity before using the confirmed distribution.'],
      ['Scope','Distribution describes sampled observable eggs; not all eggs in the videos. No automatic fits are promoted to approved data.'],
      ['Updates','Export again from the collection after changes. Counts and chart reflect the saved collection snapshot.'],
    ]:summary.append(row)
    summary.append([])
    summary.append(['Angle interval (deg)','All included','Focus + identity confirmed'])
    for lo in range(-180,180,30):
        hi=lo+30
        def count(items):return sum(lo<=s['angle_deg'] and (s['angle_deg']<hi or hi==180 and s['angle_deg']<=hi) for s in items)
        summary.append([f'{lo} to {hi}'+(' (inclusive)' if hi==180 else ''),count(active),count(confirmed)])
    chart=BarChart();chart.title='One sampled frame per egg track';chart.y_axis.title='Number of samples';chart.x_axis.title='Signed angle interval (degrees)'
    chart.x_axis.delete=False;chart.y_axis.delete=False;chart.x_axis.tickLblPos='nextTo';chart.y_axis.tickLblPos='nextTo';chart.legend.position='r';chart.x_axis.title=None;chart.title='Signed oil angle distribution (degrees)'
    chart.add_data(Reference(summary,min_col=2,max_col=3,min_row=14,max_row=26),titles_from_data=True)
    chart.set_categories(Reference(summary,min_col=1,min_row=15,max_row=26));chart.height=12;chart.width=24;summary.add_chart(chart,'E14')
    summary.column_dimensions['A'].width=37;summary.column_dimensions['B'].width=24;summary.column_dimensions['C'].width=25
    for r in range(7,13):
        summary.merge_cells(start_row=r,start_column=2,end_row=r,end_column=10);summary.cell(r,2).alignment=Alignment(wrap_text=True,vertical='center');summary.row_dimensions[r].height=32
    summary['A1'].font=Font(name='Arial',size=15,bold=True);summary.row_dimensions[1].height=26
    for c in summary[14][:3]:c.fill=PatternFill('solid',fgColor='DCEAF0');c.font=Font(bold=True);c.alignment=Alignment(wrap_text=True)
    summary.row_dimensions[14].height=30
    for sheet in wb:
        sheet.sheet_view.showGridLines=False
    temp=folder/'egg_angle_collection.tmp.xlsx';wb.save(temp);temp.replace(folder/'egg_angle_collection.xlsx')
    return folder/'egg_angle_collection.xlsx'
if __name__=='__main__':print(export(sys.argv[1]))

