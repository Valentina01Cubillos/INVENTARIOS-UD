"""Document outputs use independent workspaces, never the desktop temp directory."""
from html import escape
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from django.conf import settings
from .legacy_excel import HojaVidaService


def paragraph(value, style):
    from reportlab.platypus import Paragraph
    return Paragraph(escape('' if value is None else str(value)).replace('\n','<br/>'), style)


def generar_pdf(equipo):
    """Portable PDF with all life-cycle fields and paginated intervention records."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Image, KeepTogether
    from .forms import HOJA_CAMPOS
    from .legacy_photo import FotoService
    output=BytesIO(); styles=getSampleStyleSheet()
    styles['BodyText'].fontSize=9; styles['BodyText'].leading=12
    styles['Heading1'].textColor=colors.HexColor('#0b3c5d')
    styles['Heading2'].textColor=colors.HexColor('#0b6e4f')
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=18*mm,bottomMargin=18*mm,title=f'Hoja de vida {equipo.placa or equipo.pk}',author='LabManager UD')
    flow=[paragraph('UNIVERSIDAD DISTRITAL FRANCISCO JOSÉ DE CALDAS',styles['Heading2']),paragraph('HOJA DE VIDA DEL EQUIPO',styles['Heading1']),paragraph('Coordinación de Laboratorios · Facultad de Ingeniería',styles['BodyText']),Spacer(1,12)]
    rows=[('Laboratorio',equipo.laboratorio),('Equipo',equipo.descripcion),('Placa UD',equipo.placa),('Número interno',equipo.numero_interno),('Marca / modelo',f'{equipo.marca} / {equipo.modelo}'),('Serial',equipo.serial),('Estado',equipo.estado),('Funcionario',equipo.funcionario),('Inventario físico',equipo.inventario_fisico),('ARKA / ERP',f'{equipo.arka} / {equipo.erp}'),('Observaciones',equipo.observaciones)]
    table=Table([[paragraph(k,styles['BodyText']),paragraph(v,styles['BodyText'])] for k,v in rows],colWidths=[45*mm,129*mm])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#edf3f8')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#cbd5e1')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    flow.append(table)
    photo=equipo.foto.path if equipo.foto else FotoService().obtener_foto(equipo.marca,equipo.modelo)
    if photo and Path(photo).exists():
        img=Image(str(photo)); ratio=min(60*mm/img.imageWidth,45*mm/img.imageHeight)
        img.drawWidth=img.imageWidth*ratio; img.drawHeight=img.imageHeight*ratio
        flow.extend([Spacer(1,10),img])
    flow.extend([Spacer(1,14),paragraph('Adquisición y especificaciones',styles['Heading2'])])
    for name in HOJA_CAMPOS:
        value=equipo.datos_hoja_vida.get(name,'')
        flow.append(paragraph(f'{name}: {value if value is not None else ""}',styles['BodyText']))
    flow.extend([Spacer(1,14),paragraph('Historial de mantenimientos',styles['Heading2'])])
    maintenance=list(equipo.mantenimiento_set.select_related('tecnico').order_by('fecha','id'))
    if not maintenance: flow.append(paragraph('Sin mantenimientos registrados.',styles['BodyText']))
    for i,m in enumerate(maintenance,1):
        if m.resumen_tiempo: flow.append(paragraph(m.resumen_tiempo,styles['BodyText']))
        flow.append(paragraph(f'{i}. {m.tipo} · {m.fecha or "Fecha no registrada"}',styles['Heading3']))
        for label,value in [('Responsable',m.responsable_legacy or m.tecnico.get_full_name() or m.tecnico.username),('Empresa',m.empresa),('Garantía',m.garantia),('Diagnóstico',m.diagnostico),('Mantenimiento realizado',m.especificaciones),('Estado',m.estado),('Observaciones',m.observaciones),('Repuestos',m.repuestos),('Enlace',m.enlace_repuesto)]:
            flow.append(paragraph(f'{label}: {value}',styles['BodyText']))
        flow.append(Spacer(1,8))
    def footer(canvas,document):
        canvas.saveState(); canvas.setFont('Helvetica',8)
        canvas.drawString(18*mm,10*mm,'LabManager UD · Hoja de vida')
        canvas.drawRightString(192*mm,10*mm,f'Página {document.page}'); canvas.restoreState()
    doc.build(flow,onFirstPage=footer,onLaterPages=footer); output.seek(0)
    return output


def generar(equipo,formato):
    if formato not in ('pdf','xlsx'): raise ValueError('Formato inválido.')
    if formato=='pdf' and settings.PDF_BACKEND=='native': return generar_pdf(equipo)
    with TemporaryDirectory(prefix='labmanager-') as workspace:
        excel=HojaVidaService(workspace).generar(equipo)
        if not excel: raise RuntimeError('No se pudo generar la hoja de vida. Revise la plantilla y los registros del servidor.')
        target=Path(excel)
        if formato=='pdf':
            profile=(Path(workspace)/'lo-profile').as_uri()
            try:
                result=subprocess.run([settings.PDF_EXECUTABLE,f'-env:UserInstallation={profile}','--headless','--convert-to','pdf','--outdir',workspace,str(target)],capture_output=True,timeout=90)
            except (subprocess.TimeoutExpired,FileNotFoundError) as exc:
                raise RuntimeError('Revise LibreOffice o use PDF_BACKEND=native para generar sin Office.') from exc
            target=target.with_suffix('.pdf')
            if result.returncode or not target.exists(): raise RuntimeError('No se pudo convertir el PDF con LibreOffice.')
        return BytesIO(target.read_bytes())
