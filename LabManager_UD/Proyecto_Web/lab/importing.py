"""Lossless migration: preserve every nonempty source row, even without a safe link."""
import hashlib
import re
import unicodedata
from datetime import date, datetime, time
from pathlib import Path
from django.conf import settings
from django.db import transaction
from openpyxl import load_workbook
from .models import Auditoria, Equipo, Laboratorio, Mantenimiento, RegistroLegacy, Solicitud

def text(value):
    if value is None: return ''
    if isinstance(value, float) and value.is_integer(): return str(int(value))
    return ' '.join(str(value).split())

def key(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', text(value).upper()) if not unicodedata.combining(c))

def jsonvalue(value):
    return value.isoformat() if isinstance(value, (date, datetime, time)) else value

def parse_date(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y'):
        try: return datetime.strptime(text(value)[:10], fmt).date()
        except ValueError: pass
    return None

def parse_time(value):
    if isinstance(value, time): return value
    try: return time.fromisoformat(text(value))
    except ValueError: return None

def identifier(value):
    return '' if key(value) in ('', 'SIN PLACA', 'SIN SERIAL', 'N.A', 'N.A.', 'NA', 'NO ENCONTRADO', 'NO TIENE') else text(value)

def matching_equipment(placa, interno, serial='', laboratorio=''):
    sets = []
    for field, value in [('placa', placa), ('numero_interno', interno), ('serial', serial)]:
        value = identifier(value)
        if value:
            ids = set(Equipo.objects.filter(**{field + '__iexact': value}).values_list('pk', flat=True))
            if ids: sets.append(ids)
    if not sets: return None
    candidates = set.intersection(*sets)
    if len(candidates) > 1 and laboratorio:
        code = re.search(r'\b(60[3-9]|610|70[568])\b', text(laboratorio))
        if code:
            candidates &= set(Equipo.objects.filter(laboratorio__nombre__startswith=code.group()).values_list('pk', flat=True))
    return Equipo.objects.get(pk=next(iter(candidates))) if len(candidates) == 1 else None

def fuente(path, category, sheet=None):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet else wb.active
        headers = None
        for index, row in enumerate(ws.iter_rows(values_only=True), 1):
            normalized = [key(v) for v in row]
            if headers is None:
                found = (category == 'inventario' and 'PLACA UD' in normalized and 'DESCRIPCION' in normalized) or (category == 'hoja_vida' and 'CODIGO DE INVENTARIO' in normalized) or (category == 'reporte' and 'CONSECUTIVO' in normalized)
                if found: headers = [text(v) or f'Columna_{i+1}' for i,v in enumerate(row)]
                continue
            if not any(v is not None and text(v) for v in row): continue
            data = {h:jsonvalue(v) for h,v in zip(headers,row)}
            record,created = RegistroLegacy.objects.get_or_create(origen=f'{path.name}:{ws.title}:{index}',defaults={'archivo':path.name,'hoja':ws.title,'fila':index,'categoria':category,'datos':data,'hash_archivo':digest})
            if not created and record.datos != data:
                mark(record,'Pendiente','La fila de origen cambió; se conserva la versión importada.',record.equipo)
                yield record,None
            elif record.estado != 'Revisada': yield record,list(row)
        if headers is None: raise ValueError(f'No se encontró el encabezado en {path.name}, hoja {ws.title}')
    finally: wb.close()

def mark(record,state,reason='',equipo=None):
    record.estado,record.motivo,record.equipo=state,reason,equipo
    record.save(update_fields=['estado','motivo','equipo','actualizado'])

def get(data,*names):
    normalized={key(k):v for k,v in data.items()}
    for name in names:
        if key(name) in normalized: return normalized[key(name)]
    return ''

@transaction.atomic
def importar(user,apply=False,inventory_path=None):
    report={'aplicado':apply,'equipos':0,'solicitudes':0,'mantenimientos':0,'incidencias':[],'fuentes':[]}
    root=settings.RESOURCES_ROOT
    paths=[Path(inventory_path)] if inventory_path else sorted((root/'inventarios').glob('*.xlsx'))
    labs={'603':'Electrónica A','604':'Electrónica B','605':'Máquinas Eléctricas B','606':'Máquinas Eléctricas A','607':'Circuitos Eléctricos','608':'Centro de acopio','609':'Almacén','610':'Comunicaciones','705':'Automatización','706':'Bodega eléctrica y electrónica','708':'Control'}
    for path in paths:
        report['fuentes'].append({'archivo':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        match=re.search(r'\b(60[3-9]|610|70[568])\b',path.stem)
        code=match.group() if match else ''
        lab,_=Laboratorio.objects.get_or_create(nombre=f'{code} - {labs[code]}' if code in labs else path.stem)
        for record,row in fuente(path,'inventario','GIF-PR-003-FR-004'):
            if row is None: continue
            data=record.datos
            desc=text(get(data,'Descripción')); placa=identifier(get(data,'Placa UD')); serial=identifier(get(data,'Serial')); interno=identifier(get(data,'N. Interno'))
            if not desc or key(placa)=='PLACA UD' or key(desc)=='DESCRIPCION' or not any((placa,serial,interno)):
                mark(record,'Omitida','Encabezado, pie o fila sin descripción e identidad verificables.'); continue
            if key(placa).startswith(('REALIZO','REVISO','CLAUSULA','ELEMENTOS PENDIENTES','MOBILIARIO')):
                mark(record,'Omitida','Sección o pie del formato institucional.'); continue
            marca,_,modelo=text(get(data,'Marca y Modelo')).partition('/')
            eq,created=Equipo.objects.get_or_create(origen=record.origen,defaults={'laboratorio':lab,'placa':placa,'serial':serial,'numero_interno':interno,'descripcion':desc,'marca':marca.strip(),'modelo':modelo.strip(),'estado':text(get(data,'Estado')),'funcionario':text(get(data,'Funcionario relacionado en almacén','Funcionario relacionado')),'inventario_fisico':text(get(data,'Inventario','Inventario Físico')),'arka':text(get(data,'ARKA')),'erp':text(get(data,'ERP')),'observaciones':text(get(data,'Observaciones')),'datos_origen':data})
            report['equipos']+=int(created); mark(record,'Importada',equipo=eq)
    if not inventory_path:
        path=root/'base_datos/BASE_DATOS.xlsx'
        if path.exists():
            report['fuentes'].append({'archivo':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            for record,row in fuente(path,'hoja_vida'):
                if row is None: continue
                data=record.datos
                eq=record.equipo or matching_equipment(get(data,'CÓDIGO DE INVENTARIO'),'','',get(data,'UBICACIÓN'))
                if not eq:
                    mark(record,'Pendiente','Placa ausente, duplicada o sin equipo en los inventarios.'); continue
                if record.estado!='Importada':
                    eq.datos_hoja_vida={**data,**eq.datos_hoja_vida}; eq.save(update_fields=['datos_hoja_vida'])
                mark(record,'Importada',equipo=eq)
        path=root/'mantenimientos/REPORTE_MANTENIMIENTOS.xlsx'
        if path.exists():
            report['fuentes'].append({'archivo':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            for record,row in fuente(path,'reporte','Datos'):
                if row is None: continue
                row += [None]*max(0,27-len(row))
                names=['codigo','nombre','documento','tipo','fecha','hora','equipo','marca','placa','interno','laboratorio','asignatura','banco','descripcion','observaciones','tecnico','fecha_mantenimiento','empresa','garantia','diagnostico','especificaciones','estado_mantenimiento','repuestos','enlace','estado_solicitud','celular','tipo_solicitante']
                data={n:jsonvalue(v) for n,v in zip(names,row)}
                if not any(text(data[n]) for n in ('equipo','descripcion','placa','interno')):
                    mark(record,'Omitida','Fila de plantilla sin información de solicitud o equipo.'); continue
                eq=record.equipo or matching_equipment(row[8],row[9],laboratorio=row[10])
                states={'PENDIENTE':'Pendiente','ASIGNADA':'Asignada','FINALIZADA':'Cerrada','CERRADA':'Cerrada','CANCELADA':'Cancelada'}
                original_state=key(row[24]); state=states.get(original_state,'Pendiente')
                sol,created=Solicitud.objects.get_or_create(origen=record.origen,defaults={'equipo':eq,'solicitante':user,'tipo':text(row[3]) or 'Correctivo','descripcion':text(row[13]),'asignatura':text(row[11]),'banco':text(row[12]),'observaciones':text(row[14]),'estado':state,'codigo_legacy':text(row[0]),'datos_legacy':data,'nombre_solicitante':text(row[1]),'documento':text(row[2]),'celular':text(row[25]),'tipo_solicitante':text(row[26]),'fecha_reporte':parse_date(row[4]),'hora_reporte':parse_time(row[5])})
                report['solicitudes']+=int(created)
                fecha=parse_date(row[16]); has_intervention=fecha or any(text(row[i]) for i in (15,19,20,22))
                if has_intervention:
                    _,created=Mantenimiento.objects.get_or_create(origen=record.origen,defaults={'equipo':eq,'solicitud':sol,'tecnico':user,'fecha':fecha,'tipo':text(row[3]) or 'Correctivo','empresa':text(row[17]),'garantia':text(row[18]),'diagnostico':text(row[19]),'especificaciones':text(row[20]),'observaciones':text(row[14]),'repuestos':text(row[22]),'enlace_repuesto':text(row[23]),'responsable_legacy':text(row[15]),'estado':text(row[21]),'datos_legacy':data})
                    report['mantenimientos']+=int(created)
                reasons=[]
                if not eq: reasons.append('Registro conservado; equipo sin vincular por identidad ausente o ambigua.')
                if has_intervention and not fecha: reasons.append('Intervención histórica sin fecha de realización.')
                if original_state not in states: reasons.append('Estado original sin clasificar: '+text(row[24]))
                mark(record,'Pendiente' if reasons else 'Importada',' '.join(reasons),eq)
    for record in RegistroLegacy.objects.filter(estado='Pendiente'):
        report['incidencias'].append({'id':record.pk,'archivo':record.archivo,'fila':record.fila,'motivo':record.motivo})
    report['omitidas']=RegistroLegacy.objects.filter(estado='Omitida').count()
    report['registros_preservados']=RegistroLegacy.objects.count()
    if apply: Auditoria.objects.create(usuario=user,accion='Importar Excel',objeto='legacy',detalle=report)
    else: transaction.set_rollback(True)
    return report
