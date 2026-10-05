from __future__ import annotations

from datetime import date, datetime
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from .config import ASSETS_DIR
from .database import Database


NAVY=colors.HexColor("#123B5D")
TEAL=colors.HexColor("#0F6F78")
MINT=colors.HexColor("#60D5B7")
PALE=colors.HexColor("#EAF3F6")
INK=colors.HexColor("#152536")
MUTED=colors.HexColor("#5E7380")
RED=colors.HexColor("#B93848")
AMBER=colors.HexColor("#B66A00")
FONT_DIR=Path(reportlab.__file__).resolve().parent/"fonts"
pdfmetrics.registerFont(TTFont("EnfermeriaSans",str(FONT_DIR/"Vera.ttf")))
pdfmetrics.registerFont(TTFont("EnfermeriaSans-Bold",str(FONT_DIR/"VeraBd.ttf")))
FONT="EnfermeriaSans";FONT_BOLD="EnfermeriaSans-Bold"


def _styles():
    base=getSampleStyleSheet()
    return {
        "title":ParagraphStyle("PdfTitle",parent=base["Title"],fontName=FONT_BOLD,fontSize=22,leading=27,textColor=NAVY,alignment=TA_CENTER,spaceAfter=10),
        "subtitle":ParagraphStyle("PdfSubtitle",parent=base["Normal"],fontName=FONT,fontSize=10.5,leading=14,textColor=MUTED,alignment=TA_CENTER),
        "dossier":ParagraphStyle("DossierHeading",parent=base["Heading1"],fontName=FONT_BOLD,fontSize=17,leading=21,textColor=NAVY,spaceAfter=8,keepWithNext=True),
        "section":ParagraphStyle("PdfSection",parent=base["Heading2"],fontName=FONT_BOLD,fontSize=11.5,leading=14,textColor=TEAL,spaceBefore=8,spaceAfter=5,keepWithNext=True),
        "body":ParagraphStyle("PdfBody",parent=base["BodyText"],fontName=FONT,fontSize=8.5,leading=11,textColor=INK),
        "small":ParagraphStyle("PdfSmall",parent=base["BodyText"],fontName=FONT,fontSize=7.2,leading=9,textColor=MUTED),
        "smallRight":ParagraphStyle("PdfSmallRight",parent=base["BodyText"],fontName=FONT,fontSize=7.2,leading=9,textColor=MUTED,alignment=TA_RIGHT),
        "center":ParagraphStyle("PdfCenter",parent=base["BodyText"],fontName=FONT,fontSize=8.5,leading=11,textColor=INK,alignment=TA_CENTER),
        "warning":ParagraphStyle("PdfWarning",parent=base["BodyText"],fontName=FONT_BOLD,fontSize=8.5,leading=11,textColor=RED),
    }


STYLES=_styles()


def _p(value, style="body"):
    text="-" if value in (None,"") else str(value)
    return Paragraph(escape(text).replace("\n","<br/>"),STYLES[style])


class DossierDocument(BaseDocTemplate):
    def __init__(self,filename,**kwargs):
        super().__init__(filename,pagesize=A4,leftMargin=1.35*cm,rightMargin=1.35*cm,topMargin=1.45*cm,bottomMargin=1.35*cm,**kwargs)
        frame=Frame(self.leftMargin,self.bottomMargin,self.width,self.height,id="normal")
        self.addPageTemplates(PageTemplate(id="main",frames=frame,onPage=self._decorate))

    def _decorate(self,canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor("#B7CAD3"));canvas.setLineWidth(.5)
        canvas.line(self.leftMargin,1.05*cm,A4[0]-self.rightMargin,1.05*cm)
        canvas.setFont(FONT,7);canvas.setFillColor(MUTED)
        canvas.drawString(self.leftMargin,.68*cm,"Enfermería San Giuseppe Moscati · Documento confidencial")
        canvas.drawRightString(A4[0]-self.rightMargin,.68*cm,f"Página {doc.page}")
        canvas.restoreState()

    def afterFlowable(self,flowable):
        if isinstance(flowable,Paragraph) and flowable.style.name=="DossierHeading":
            text=flowable.getPlainText();key=f"dossier-{self.seq.nextf('dossier')}"
            self.canv.bookmarkPage(key);self.canv.addOutlineEntry(text,key,level=0,closed=False)
            self.notify("TOCEntry",(0,text,self.page,key))


def _photo(blob):
    if blob:
        try:
            image=Image(BytesIO(blob),width=3.05*cm,height=3.85*cm,kind="proportional")
            image.hAlign="CENTER";return image
        except Exception:
            pass
    placeholder=Table([[_p("SIN FOTO","center")]],colWidths=[3.05*cm],rowHeights=[3.85*cm])
    placeholder.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.8,colors.HexColor("#9DB4BE")),("BACKGROUND",(0,0),(-1,-1),PALE),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    return placeholder


def _institutional_header(db:Database):
    institution=db.get_setting("institution_name","Seminario Mayor de Guayaquil")
    clinic=db.get_setting("clinic_name","Enfermería San Giuseppe Moscati")
    logo_path=ASSETS_DIR/"seminario_logo.png"
    if logo_path.exists():
        logo=Image(str(logo_path),width=1.55*cm,height=1.55*cm,kind="proportional");logo.hAlign="CENTER"
    else:logo=_p("SM","center")
    left=Table([[_p(institution,"small")],[_p("GUAYAQUIL","small")]],colWidths=[8.0*cm])
    right=Table([[_p("ENFERMERÍA","smallRight")],[_p(clinic,"smallRight")]],colWidths=[6.6*cm])
    header=Table([[logo,left,right]],colWidths=[1.8*cm,8.0*cm,6.6*cm],rowHeights=[1.65*cm])
    header.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(2,0),(2,0),"RIGHT"),
        ("LINEBELOW",(0,0),(-1,-1),1,TEAL),("LEFTPADDING",(0,0),(-1,-1),4),
        ("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]));return header


def _section(title, rows, widths=(4.2*cm,12.2*cm)):
    data=[[Paragraph(escape(title),STYLES["section"]),""]]
    for label,value in rows:data.append([_p(label,"small"),_p(value)])
    table=Table(data,colWidths=list(widths),hAlign="LEFT")
    table.setStyle(TableStyle([
        ("SPAN",(0,0),(-1,0)),("BACKGROUND",(0,0),(-1,0),PALE),("LINEBELOW",(0,0),(-1,0),.8,TEAL),
        ("FONTNAME",(0,1),(0,-1),FONT_BOLD),("TEXTCOLOR",(0,1),(0,-1),MUTED),
        ("GRID",(0,1),(-1,-1),.35,colors.HexColor("#C8D7DD")),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]));return table


def _age(birth_date):
    try:
        born=date.fromisoformat(birth_date);today=date.today();return today.year-born.year-((today.month,today.day)<(born.month,born.day))
    except Exception:return None


def _profile_header(row):
    age=_age(row["birth_date"]);name=f"{row['first_name']} {row['last_name']}"
    summary=Table([
        [_p(name,"dossier")],
        [_p(f"Expediente N.° {row['id']} · {'Activo' if not row['archived'] else 'Archivado'}","small")],
        [_p(f"Año de formación: {row['formation_year'] or '-'}   ·   Habitación: {row['room'] or '-'}","body")],
        [_p(f"Diócesis: {row['diocese'] or '-'}","body")],
        [_p(f"Fecha de nacimiento: {row['birth_date'] or '-'}"+(f"   ·   Edad: {age} años" if age is not None else ""),"body")],
    ],colWidths=[12.7*cm])
    head=Table([[_photo(row["photo"]),summary]],colWidths=[3.5*cm,12.9*cm])
    head.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("BOX",(0,0),(-1,-1),.8,NAVY),("BACKGROUND",(1,0),(1,0),colors.white),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    return head


def _profile_sections(row):
    return [
        _section("Datos personales",[("Identificación",row["external_id"]),("Nacionalidad",row["nationality"]),("Lugar de nacimiento",", ".join(x for x in (row["birth_city"],row["birth_country"]) if x))]),
        Spacer(1,5),
        _section("Procedencia eclesiástica",[("Diócesis",row["diocese"]),("Parroquia",row["parish"])]),
        Spacer(1,5),
        _section("Domicilio y contacto",[("Dirección",row["address"]),("Barrio o sector",row["neighborhood"]),("Ciudad / provincia",", ".join(x for x in (row["city"],row["province"]) if x)),("País",row["country"]),("Teléfono",row["personal_phone"]),("Correo",row["email"])]),
        Spacer(1,5),
        _section("Información sanitaria esencial",[("Grupo sanguíneo",row["blood_type"]),("Alergias",row["allergies"]),("Condiciones importantes",row["important_conditions"]),("Medicamentos permanentes",row["permanent_medicines"]),("Restricciones alimentarias",row["dietary_restrictions"]),("Centro de salud",row["health_center"]),("Seguro",row["insurance"])]),
        Spacer(1,5),
        _section("Contacto de emergencia",[("Nombre",row["emergency_contact"]),("Parentesco",row["emergency_relation"]),("Teléfono",row["emergency_phone"])]),
        Spacer(1,5),
        _section("Observaciones generales",[("Observaciones",row["notes"]),("Actualización",row["updated_at"])]),
    ]


def _control_summary(control):
    pressure=f"{control['systolic']}/{control['diastolic']} mmHg" if control["systolic"] and control["diastolic"] else "-"
    context={"fasting":"Ayunas","postprandial":"Después de comer","random":"Aleatoria","":"No especificada"}.get(control["glucose_context"],control["glucose_context"])
    rows=[
        ["Fecha",str(control["measured_at"]).replace("T"," ")[:16],"Estado","ANULADO" if control["voided_at"] else "Vigente"],
        ["Peso",f"{control['weight_kg']} kg" if control["weight_kg"] else "-","Estatura",f"{control['height_cm']} cm" if control["height_cm"] else "-"],
        ["IMC",control["bmi"] or "-","Presión",pressure],
        ["Pulso",f"{control['pulse']} lpm" if control["pulse"] else "-","Glucosa",f"{control['glucose_mg_dl']} mg/dL ({context})" if control["glucose_mg_dl"] else "-"],
        ["SpO2",f"{control['oxygen_saturation']} %" if control["oxygen_saturation"] else "-","Temperatura",f"{control['temperature_c']} °C" if control["temperature_c"] else "-"],
        ["Observaciones",control["notes"] or "-","Derivación",control["referral"] or "-"],
        ["Registrado por",control["recorded_by"] or "-","Motivo anulación",control["void_reason"] or "-"],
    ]
    data=[]
    for row in rows:data.append([_p(row[0],"small"),_p(row[1]),_p(row[2],"small"),_p(row[3],"warning" if row[2]=="Estado" and control["voided_at"] else "body")])
    t=Table(data,colWidths=[2.5*cm,5.5*cm,2.5*cm,5.9*cm],repeatRows=0)
    t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.35,colors.HexColor("#C8D7DD")),("BACKGROUND",(0,0),(0,-1),PALE),("BACKGROUND",(2,0),(2,-1),PALE),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    return t


def _history_table(controls):
    data=[[_p(x,"small") for x in ("Fecha","Peso","IMC","Presión","Pulso","Glucosa","SpO2","Temp.","Estado")]]
    for c in controls:
        pressure=f"{c['systolic']}/{c['diastolic']}" if c["systolic"] and c["diastolic"] else "-"
        state="Anulado" if c["voided_at"] else "Vigente"
        data.append([_p(str(c["measured_at"]).replace("T"," ")[:16],"small"),_p(c["weight_kg"] or "-","small"),_p(c["bmi"] or "-","small"),_p(pressure,"small"),_p(c["pulse"] or "-","small"),_p(c["glucose_mg_dl"] or "-","small"),_p(c["oxygen_saturation"] or "-","small"),_p(c["temperature_c"] or "-","small"),_p(state,"warning" if c["voided_at"] else "small")])
    t=Table(data,colWidths=[2.4*cm,1.35*cm,1.15*cm,1.55*cm,1.25*cm,1.45*cm,1.3*cm,1.25*cm,1.6*cm],repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#B7CAD3")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F4F8FA")]),("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    return t


def _signature_block():
    t=Table([["",""] ,[_p("Firma del encargado de Enfermería","center"),_p("Firma del seminarista (opcional)","center")]],colWidths=[7.7*cm,7.7*cm],rowHeights=[1.25*cm,.5*cm])
    t.setStyle(TableStyle([("LINEABOVE",(0,1),(0,1),.6,INK),("LINEABOVE",(1,1),(1,1),.6,INK),("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12)]));return t


def _dossier_story(db:Database,seminarian_id:int,include_page_break=True):
    rows=db.query("SELECT * FROM seminarians WHERE id=?",(seminarian_id,))
    if not rows:raise ValueError("El expediente de salud del seminarista no existe.")
    row=rows[0];controls=db.query("SELECT * FROM medical_controls WHERE seminarian_id=? AND voided_at IS NULL ORDER BY measured_at DESC,id DESC",(seminarian_id,))
    story=[]
    if include_page_break:story.append(PageBreak())
    heading=Paragraph(escape(f"Expediente de salud - {row['first_name']} {row['last_name']}"),STYLES["dossier"]);story.extend([_institutional_header(db),Spacer(1,8),heading,_profile_header(row),Spacer(1,8),*_profile_sections(row),Spacer(1,8)])
    story.append(Paragraph("Control de salud más reciente",STYLES["section"]))
    story.append(_control_summary(controls[0]) if controls else _p("No existen controles de salud registrados."))
    if controls:
        story.extend([Spacer(1,8),Paragraph("Historial de controles",STYLES["section"]),_history_table(controls),Spacer(1,8),Paragraph("Detalle de controles",STYLES["section"])])
        for index,control in enumerate(controls,1):
            story.append(KeepTogether([_p(f"Control {index} - {str(control['measured_at']).replace('T',' ')[:16]}","small"),Spacer(1,2),_control_summary(control),Spacer(1,6)]))
    deliveries=db.query("""SELECT m.*,i.name AS item_name FROM movements m JOIN items i ON i.id=m.item_id
        WHERE m.seminarian_id=? AND m.voided_at IS NULL AND m.type IN ('delivery','administered')
        ORDER BY m.occurred_at DESC,m.id DESC""",(seminarian_id,))
    story.extend([Spacer(1,8),Paragraph("Medicamentos entregados y dosis administradas",STYLES["section"])])
    if deliveries:
        for movement in deliveries:
            label="Dosis administrada" if movement["type"]=="administered" else "Entrega"
            story.extend([_section(str(movement["occurred_at"]).replace("T"," ")[:16],[
                ("Medicamento",movement["item_name"]),("Registro",label),("Cantidad",movement["quantity"]),
                ("Dosis",movement["dose"]),("Motivo",movement["reason"])]),Spacer(1,6)])
    else:story.append(_p("No existen entregas ni dosis administradas registradas."))
    story.extend([Spacer(1,12),_signature_block(),Spacer(1,8),_p("Documento de seguimiento sanitario. No constituye diagnóstico ni sustituye la valoración médica.","small")])
    return story


def _cover(db:Database,count:int):
    clinic=db.get_setting("clinic_name","Enfermería San Giuseppe Moscati");institution=db.get_setting("institution_name","Seminario Mayor de Guayaquil");manager=db.get_setting("manager_name","")
    story=[Spacer(1,.35*cm)]
    logo_path=ASSETS_DIR/"seminario_logo.png"
    if logo_path.exists():
        logo=Image(str(logo_path),width=3.1*cm,height=3.1*cm,kind="proportional");logo.hAlign="CENTER"
        badge=Table([[logo]],colWidths=[3.45*cm],rowHeights=[3.45*cm],hAlign="CENTER");badge.setStyle(TableStyle([("ALIGN",(0,0),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.extend([badge,Paragraph(escape(institution),STYLES["subtitle"]),Spacer(1,7)])
    saint=ASSETS_DIR/"san_giuseppe_moscati.png"
    if saint.exists():
        image=Image(str(saint),width=4.2*cm,height=5.5*cm,kind="proportional");image.hAlign="CENTER";story.extend([image,Spacer(1,7)])
    story.extend([Paragraph("ENFERMERÍA",STYLES["title"]),Paragraph(escape(clinic),STYLES["subtitle"]),Spacer(1,12),Paragraph("EXPEDIENTES DE SALUD",STYLES["title"]),Spacer(1,12),_section("Información del documento",[("Institución",institution),("Encargado",manager),("Fecha de generación",datetime.now().strftime("%d/%m/%Y %H:%M")),("Seminaristas incluidos",count)]),Spacer(1,18),_p("CONFIDENCIAL - Contiene información personal de salud. Debe conservarse bajo custodia del responsable de Enfermería.","warning")])
    return story


def export_control_pdf(db:Database,control_id:int,filename:str|Path):
    rows=db.query("""SELECT c.*,s.first_name,s.last_name,s.external_id,s.diocese,s.formation_year,s.room,s.blood_type,s.allergies,s.photo
        FROM medical_controls c JOIN seminarians s ON s.id=c.seminarian_id WHERE c.id=?""",(control_id,))
    if not rows:raise ValueError("El control de salud no existe.")
    c=rows[0];doc=DossierDocument(str(filename),title="Registro de control de salud")
    mini=Table([[_photo(c["photo"]),Table([[_p(f"{c['first_name']} {c['last_name']}","dossier")],[_p(f"Identificación: {c['external_id'] or '-'} · Diócesis: {c['diocese'] or '-'}","body")],[_p(f"Año: {c['formation_year'] or '-'} · Habitación: {c['room'] or '-'} · Sangre: {c['blood_type'] or '-'}","body")],[_p(f"Alergias: {c['allergies'] or 'No registradas'}","warning" if c["allergies"] else "body")]],colWidths=[12.7*cm])]],colWidths=[3.5*cm,12.9*cm])
    mini.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.8,NAVY),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story=[_institutional_header(db),Spacer(1,8),Paragraph("Registro de control de salud",STYLES["title"]),Paragraph("Enfermería San Giuseppe Moscati",STYLES["subtitle"]),Spacer(1,10),mini,Spacer(1,10),_control_summary(c),Spacer(1,18),_signature_block(),Spacer(1,10),_p("Documento de seguimiento de salud. No constituye diagnóstico ni sustituye la valoración médica.","small")]
    doc.multiBuild(story)


def export_seminarian_dossier_pdf(db:Database,seminarian_id:int,filename:str|Path):
    doc=DossierDocument(str(filename),title="Expediente de salud del seminarista")
    doc.multiBuild(_dossier_story(db,seminarian_id,False))


def export_emergency_summary_pdf(db:Database,seminarian_id:int,filename:str|Path,generated_by:str=""):
    rows=db.query("SELECT * FROM seminarians WHERE id=?",(seminarian_id,))
    if not rows:raise ValueError("El expediente de salud del seminarista no existe.")
    row=rows[0];control_rows=db.query("SELECT * FROM medical_controls WHERE seminarian_id=? AND voided_at IS NULL ORDER BY measured_at DESC,id DESC LIMIT 1",(seminarian_id,))
    age=_age(row["birth_date"]);generated=datetime.now().strftime("%d/%m/%Y %H:%M")
    identity=Table([[_photo(row["photo"]),Table([
        [_p(f"{row['first_name']} {row['last_name']}","dossier")],
        [_p(f"Identificación: {row['external_id'] or '-'} · Edad: {str(age)+' años' if age is not None else '-'}")],
        [_p(f"Formación: {row['formation_year'] or '-'} · Habitación: {row['room'] or '-'}")],
        [_p(f"Diócesis: {row['diocese'] or '-'}")],
        [_p(f"GRUPO SANGUÍNEO: {row['blood_type'] or 'NO CONSTA'}","warning" if not row["blood_type"] else "body")],
    ],colWidths=[12.7*cm])]],colWidths=[3.5*cm,12.9*cm])
    identity.setStyle(TableStyle([("BOX",(0,0),(-1,-1),1,NAVY),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story=[_institutional_header(db),Spacer(1,8),Paragraph("Resumen de salud para emergencias",STYLES["title"]),
           Paragraph("Resumen esencial para atención inmediata",STYLES["subtitle"]),Spacer(1,10),identity,Spacer(1,9),
           _section("Alertas sanitarias",[("Alergias",row["allergies"] or "No registradas"),("Condiciones importantes",row["important_conditions"] or "No registradas"),("Medicamentos permanentes",row["permanent_medicines"] or "Ninguno registrado"),("Restricciones alimentarias",row["dietary_restrictions"] or "No registradas")]),Spacer(1,7),
           _section("Contacto y atención",[("Contacto de emergencia",row["emergency_contact"]),("Parentesco",row["emergency_relation"]),("Teléfono",row["emergency_phone"]),("Centro de salud",row["health_center"]),("Seguro",row["insurance"])]),Spacer(1,7)]
    story.extend([Paragraph("Último control de salud vigente",STYLES["section"]),_control_summary(control_rows[0]) if control_rows else _p("No existen controles de salud vigentes registrados."),Spacer(1,10),
                  _section("Emisión",[("Generado por",generated_by or "Encargado no registrado"),("Fecha y hora",generated),("Expediente",f"N.° {row['id']}")]),Spacer(1,8),
                  _p("CONFIDENCIAL. Este resumen contiene datos registrados en la Enfermería. No sustituye la valoración clínica ni confirma por sí solo el grupo sanguíneo.","warning")])
    DossierDocument(str(filename),title="Resumen de salud para emergencias").multiBuild(story)


def export_all_dossiers_pdf(db:Database,filename:str|Path):
    seminarians=db.query("SELECT id,first_name,last_name FROM seminarians WHERE archived=0 ORDER BY last_name,first_name")
    doc=DossierDocument(str(filename),title="Expedientes de salud")
    toc=TableOfContents();toc.levelStyles=[ParagraphStyle("TOCLevel",fontName=FONT,fontSize=9,leading=12,leftIndent=10,firstLineIndent=-10,textColor=INK)]
    story=_cover(db,len(seminarians))+[PageBreak(),Paragraph("Índice por seminarista",STYLES["title"]),Spacer(1,8),toc]
    for row in seminarians:story.extend(_dossier_story(db,row["id"],True))
    doc.multiBuild(story)
