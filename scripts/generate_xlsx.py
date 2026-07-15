# -*- coding: utf-8 -*-
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
AREA=51900; GEL=2.70
fire_rate=(460000-(4.12+1.50+0.75+0.60)*AREA-555.56-450.00)/AREA
wb=openpyxl.Workbook(); ws=wb.active; ws.title="Prices 460000"
thin=Side(style='thin', color='999999'); bd=Border(thin,thin,thin,thin)
hf=PatternFill('solid', fgColor='D9D9D9'); tf=PatternFill('solid', fgColor='EEF3FF')
bold=Font(bold=True)
hdr=["Service (EN)","Услуга (RU)","Type","Price USD","Price GEL","Qty (m²)","Amount USD"]
ws.append(hdr)
for c in ws[1]: c.font=bold; c.fill=hf; c.border=bd; c.alignment=Alignment(wrap_text=True,vertical='center')
rows=[
 ("Architectural project","Архитектурный проект","per m²",4.12,4.12*GEL,AREA),
 ("Structural project (with expert review)","Конструктивный проект (с экспертизой)","per m²",1.50,1.50*GEL,AREA),
 ("Engineering systems (electrical, water & sewage)","Инженерные системы","per m²",0.75,0.75*GEL,AREA),
 ("Fire safety & accessibility (Code 41)","Пожарная безопасность (Код 41)","per m²",0.60,0.60*GEL,AREA),
 ("Fire protection systems (range 1.50–2.25)","Системы пожаротушения (диапазон)","per m²",round(fire_rate,4),round(fire_rate*GEL,4),AREA),
 ("Transport circulation schemes","Транспортные схемы","lump sum",555.56,1500.0,1),
 ("Business plan for land status change","Бизнес-план (смена статуса земли)","lump sum",450.00,1215.0,1),
]
for en,ru,typ,usd,gel,qty in rows:
    amt=usd*qty
    ws.append([en,ru,typ,usd,gel,qty,round(amt,2)])
for r in ws.iter_rows(min_row=2, max_row=1+len(rows)):
    for c in r: c.border=bd
    r[3].number_format='$#,##0.00'; r[4].number_format='#,##0.00" GEL"'; r[6].number_format='$#,##0.00'
tr=ws.max_row+1
ws.cell(tr,1,"TOTAL / ИТОГО").font=bold
ws.cell(tr,7,f"=SUM(G2:G{ws.max_row})").font=bold
ws.cell(tr,7).number_format='$#,##0.00'
for col in range(1,8): ws.cell(tr,col).fill=tf; ws.cell(tr,col).border=bd
ws.cell(tr+2,1,"Target / Цель:").font=bold; ws.cell(tr+2,2,"$460,000.00 for 51,900 m²")
ws.cell(tr+3,1,"Factor / Коэффициент:").font=bold; ws.cell(tr+3,2,"≈ 0.749 (−25.1%) applied proportionally")
widths=[46,40,11,13,15,11,15]
for i,w in enumerate(widths,1): ws.column_dimensions[chr(64+i)].width=w
ws.freeze_panes="A2"
wb.save("Price_Calculation_460000.xlsx")
print("XLSX saved")
