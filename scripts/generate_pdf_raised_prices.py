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

# Original prices raised +12.5% (within 10-15%); GEL = USD x 2.70
table_rows = [
    ("Service (EN)", "Price USD", "Price GEL"),
    ("Architectural project", "$6.19 / m²", "16.71 GEL / m²"),
    ("Structural project (with expert review)", "$2.25 / m²", "6.08 GEL / m²"),
    ("Engineering systems (electrical, water & sewage)", "$1.12 / m²", "3.02 GEL / m²"),
    ("Fire safety & accessibility (Code 41)", "$0.90 / m²", "2.43 GEL / m²"),
    ("Fire protection systems", "Approx. $2.25–3.38 / m²", "Approx. 6.08–9.11 GEL / m²"),
    ("Transport circulation schemes", "$833.33", "2250 GEL"),
    ("Business plan for land status change", "$675", "1822.50 GEL"),
]

doc = SimpleDocTemplate("Design_Services_EN_RU_updated.pdf", pagesize=A4,
                        leftMargin=18*mm, rightMargin=18*mm, topMargin=20*mm, bottomMargin=18*mm)
el = []
# Title WITHOUT "R312"
el.append(P("Design Services &amp; Prices (English / Russian)", size=22, bold=False))
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
print("PDF built (no R312, +12.5%).")
