# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph,
                                Spacer)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))

AREA = 51900
GEL = 2.70

# Final adjusted figures (verified total = $460,000.00)
fire_rate = (460000 - (4.12+1.50+0.75+0.60)*AREA - 555.56 - 450.00)/AREA  # 1.873824...

rows_pm = [
    ("Architectural project", "Архитектурный проект", 4.12),
    ("Structural project (with expert review)", "Конструктивный проект (с экспертизой)", 1.50),
    ("Engineering systems (electrical, water & sewage)", "Инженерные системы (эл-во, вода, канализация)", 0.75),
    ("Fire safety & accessibility (Code 41)", "Пожарная безопасность и доступность (Код 41)", 0.60),
]
fire = ("Fire protection systems", "Системы пожаротушения", fire_rate)  # display range
fixed = [
    ("Transport circulation schemes", "Транспортные схемы движения", 555.56, 1500.0),
    ("Business plan for land status change", "Бизнес-план для изменения статуса земли", 450.00, 1215.0),
]

styles = getSampleStyleSheet()
def P(txt, font='DejaVu', size=9, bold=False, color=colors.black, align=TA_LEFT):
    st = ParagraphStyle('x', fontName=('DejaVu-Bold' if bold else font), fontSize=size,
                        leading=size*1.25, textColor=color, alignment=align)
    return Paragraph(txt, st)

doc = SimpleDocTemplate("Corrected_Design_Services_Prices_460000.pdf", pagesize=A4,
                        leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=16*mm)
el = []
el.append(P("R312 Design Services &amp; Prices (English / Russian)", size=17, bold=True))
el.append(Spacer(1, 3*mm))
el.append(P("Project area / Площадь проекта: <b>51,900 m²</b> &nbsp;·&nbsp; "
            "Exchange rate / Курс: <b>1 USD = 2.70 GEL</b>", size=9))
el.append(Spacer(1, 4*mm))

# Table header
hdr = [P("Service (EN)", bold=True, size=9), P("Услуга (RU)", bold=True, size=9),
       P("Price USD", bold=True, size=9), P("Price GEL", bold=True, size=9),
       P("Amount for 51,900 m²<br/>(USD)", bold=True, size=9)]
data = [hdr]

def money(x): return "{:,.2f}".format(x)

for en, ru, rate in rows_pm:
    amt = rate*AREA
    data.append([P(en,size=9), P(ru,size=9),
                 P(f"${rate:.2f} / m²",size=9), P(f"{rate*GEL:.2f} GEL / m²",size=9),
                 P(f"${money(amt)}",size=9, align=2)])
# fire protection as range, amount = its balancing contribution
fire_amt = fire[2]*AREA
data.append([P(fire[0],size=9), P(fire[1],size=9),
             P("≈ $1.87 / m²<br/>(range $1.50–2.25)",size=9),
             P("≈ 5.06 GEL / m²<br/>(4.05–6.08)",size=9),
             P(f"${money(fire_amt)}",size=9, align=2)])
for en, ru, usd, gel in fixed:
    data.append([P(en,size=9), P(ru,size=9),
                 P(f"${usd:,.2f}",size=9), P(f"{gel:,.0f} GEL",size=9),
                 P(f"${money(usd)}",size=9, align=2)])

total = sum(r[2]*AREA for r in rows_pm) + fire_amt + sum(f[2] for f in fixed)
data.append([P("TOTAL / ИТОГО", bold=True, size=10), P("", size=9), P("", size=9), P("", size=9),
             P(f"<b>${money(total)}</b>", bold=True, size=10, align=2)])

col_w = [46*mm, 46*mm, 26*mm, 26*mm, 30*mm]
t = Table(data, colWidths=col_w, repeatRows=1)
t.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#d9d9d9')),
    ('BACKGROUND',(0,-1),(-1,-1), colors.HexColor('#eef3ff')),
    ('GRID',(0,0),(-1,-1), 0.5, colors.HexColor('#999999')),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
    ('SPAN',(0,-1),(3,-1)),
]))
el.append(t)
el.append(Spacer(1, 4*mm))
el.append(P("Package total for the entire 51,900 m² area = <b>$460,000.00</b> · "
            "Итог по всей площади 51 900 м² = <b>$460 000.00</b>", size=9, bold=False))
el.append(Spacer(1, 6*mm))

note_en = ("<b>English</b><br/>"
    "Geological survey is not included because its scope and methodology depend on the "
    "structural engineer's requirements and cannot be priced in advance.<br/><br/>"
    "Taxation (inventory of existing trees/shrubs) and dendrological project are also "
    "excluded because the cost depends on the number of existing trees and shrubs and "
    "can only be determined after a site survey.")
note_ru = ("<b>Русский</b><br/>"
    "Стоимость геологического исследования не включена, так как объём и методика "
    "зависят от требований конструктора и не могут быть определены заранее.<br/><br/>"
    "Таксация (инвентаризация деревьев и кустарников) и дендрологический проект "
    "также не включены в стоимость, поскольку цена зависит от количества "
    "существующих деревьев и кустарников и определяется только после обследования участка.")
el.append(P(note_en, size=8.5))
el.append(Spacer(1, 3*mm))
el.append(P(note_ru, size=8.5))

doc.build(el)
print("PDF built. Total = $%.2f" % total)
