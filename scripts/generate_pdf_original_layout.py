# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT

pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVu-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))

def P(txt, size=11, bold=False):
    st = ParagraphStyle('x', fontName=('DejaVu-Bold' if bold else 'DejaVu'),
                        fontSize=size, leading=size*1.3, alignment=TA_LEFT)
    return Paragraph(txt, st)

# Corrected prices (same layout as original: Service EN | Price USD | Price GEL)
table_rows = [
    ("Service (EN)", "Price USD", "Price GEL"),  # header
    ("Architectural project", "$4.12 / m²", "11.12 GEL / m²"),
    ("Structural project (with expert review)", "$1.50 / m²", "4.05 GEL / m²"),
    ("Engineering systems (electrical, water & sewage)", "$0.75 / m²", "2.03 GEL / m²"),
    ("Fire safety & accessibility (Code 41)", "$0.60 / m²", "1.62 GEL / m²"),
    ("Fire protection systems", "Approx. $1.50–2.25 / m²", "Approx. 4.05–6.08 GEL / m²"),
    ("Transport circulation schemes", "$555.56", "1500 GEL"),
    ("Business plan for land status change", "$450", "1215 GEL"),
]

doc = SimpleDocTemplate("Design_Services_EN_RU2_corrected.pdf", pagesize=A4,
                        leftMargin=18*mm, rightMargin=18*mm, topMargin=20*mm, bottomMargin=18*mm)
el = []
el.append(P("R312 Design Services &amp; Prices (English /<br/>Russian)", size=22, bold=False))
el.append(Spacer(1, 5*mm))

data = []
for i,(a,b,c) in enumerate(table_rows):
    bold = (i==0)
    data.append([P(a,size=11,bold=bold), P(b,size=11,bold=bold), P(c,size=11,bold=bold)])

t = Table(data, colWidths=[92*mm, 38*mm, 44*mm])
t.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,0), colors.HexColor('#d9d9d9')),
    ('GRID',(0,0),(-1,-1), 0.75, colors.HexColor('#b0b0b0')),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
]))
el.append(t)
el.append(Spacer(1, 8*mm))

en = ("English<br/>"
    "Geological survey is not included because its scope and methodology depend on the "
    "structural engineer's requirements and cannot be priced in advance.<br/><br/>"
    "Taxation (inventory of existing trees/shrubs) and dendrological project are also "
    "excluded because the cost depends on the number of existing trees and shrubs and "
    "can only be determined after a site survey.")
ru = ("Русский<br/>"
    "Стоимость геологического исследования не включена, так как объем и методика "
    "зависят от требований конструктора и не могут быть определены заранее.<br/><br/>"
    "Таксация (инвентаризация деревьев и кустарников) и дендрологический проект "
    "также не включены в стоимость, поскольку цена зависит от количества "
    "существующих деревьев и кустарников и определяется только после "
    "обследования участка.")
el.append(P(en, size=11))
el.append(Spacer(1, 5*mm))
el.append(P(ru, size=11))

doc.build(el)

# sanity check total
AREA=51900
pm = 4.12+1.50+0.75+0.60 + (460000-(4.12+1.50+0.75+0.60)*AREA-555.56-450)/AREA
tot = pm*AREA + 555.56 + 450
print("PDF built. Implied package total = $%.2f" % tot)
