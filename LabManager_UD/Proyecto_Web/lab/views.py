from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import json
import zipfile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F, Count
from django.http import FileResponse, HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from django.utils import timezone
from openpyxl import Workbook
from PIL import Image

from .models import Equipo, Laboratorio, Solicitud, Mantenimiento, Auditoria, RegistroLegacy, TrabajoDocumento
from .models import Traslado,AparienciaPerfil
from .transfers import puede_editar, exigir_edicion, pedir, resolver
from .forms import (EquipoForm, SolicitudForm, SolicitarMantenimientoForm, MantenimientoForm, HojaVidaForm, FotoForm,
                    CancelarForm, ConciliarForm, ImportarForm, LaboratorioForm, UsuarioForm, PerfilForm, AparienciaForm, EditarUsuarioForm)


def snapshot(obj):
    return {field.name: str(getattr(obj, field.attname)) if getattr(obj, field.attname) is not None else None
            for field in obj._meta.fields if field.name not in ('password',)}

def audit(user, action, obj, before=None, detail=None):
    Auditoria.objects.create(usuario=user, accion=action, objeto=f'{obj._meta.label}:{obj.pk}',
        detalle=detail or {'antes': before or {}, 'despues': snapshot(obj)})

def solicitudes_visibles(user):
    qs=Solicitud.objects.select_related('equipo','equipo__laboratorio','solicitante','tecnico')
    return qs if user.is_authenticated else qs.none()

def mantenimientos_visibles(user):
    qs=Mantenimiento.objects.select_related('equipo','equipo__laboratorio','solicitud','tecnico')
    if user.has_perm('lab.view_mantenimiento'): return qs
    return qs.none()

def inventory(request):
    qs=Equipo.objects.select_related('laboratorio').order_by('laboratorio__nombre','numero_interno','id')
    q=request.GET.get('q','').strip()
    if q: qs=qs.filter(Q(placa__icontains=q)|Q(numero_interno__icontains=q)|Q(serial__icontains=q)|Q(descripcion__icontains=q)|Q(marca__icontains=q)|Q(modelo__icontains=q)|Q(laboratorio__nombre__icontains=q))
    lab=request.GET.get('laboratorio','')
    if lab.isdigit(): qs=qs.filter(laboratorio_id=int(lab))
    if request.GET.get('estado'): qs=qs.filter(estado=request.GET['estado'])
    return qs

def paginate(request, qs, size=30):
    return Paginator(qs,size).get_page(request.GET.get('page'))

@login_required
def inicio(request):
    labs=Laboratorio.objects.filter(responsable=request.user).annotate(total=Count('equipo')).order_by('nombre')
    qs=Equipo.objects.filter(laboratorio__responsable=request.user)
    metrics={
        'Equipos':qs.count() if request.user.has_perm('lab.view_equipo') else 0,
        'Activos':qs.filter(estado__icontains='activo').exclude(estado__icontains='inactivo').count(),
        'Dañados':qs.filter(estado__icontains='dañado').count(),
        'En mantenimiento':qs.filter(estado__icontains='mantenimiento').count(),
        'Obsoletos':qs.filter(estado__icontains='obsoleto').count(),
        'Laboratorios':labs.count(),
    }
    return render(request,'inicio.html',{'metrics':metrics,'mis_laboratorios':labs,'pendientes':solicitudes_visibles(request.user).filter(estado='Pendiente').count(),
        'recientes':solicitudes_visibles(request.user).order_by('-id')[:6],
        'conciliar':RegistroLegacy.objects.filter(estado='Pendiente').count() if request.user.has_perm('lab.importar_datos') else None})

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def equipos(request):
    qs=inventory(request)
    modo_hojas=request.path.startswith('/hojas-vida/')
    laboratorio_seleccionado=Laboratorio.objects.filter(pk=int(request.GET['laboratorio'])).first() if request.GET.get('laboratorio','').isdigit() else None
    return render(request,'equipos.html',{'page':paginate(request,qs),'q':request.GET.get('q',''),
        'laboratorio_seleccionado':laboratorio_seleccionado,
        'mostrar_equipos':modo_hojas or bool(request.GET.get('q','').strip() or request.GET.get('laboratorio') or request.GET.get('estado') or request.GET.get('todos')),
        'laboratorios':Laboratorio.objects.annotate(total=Count('equipo')).order_by('nombre'),
        'estados':Equipo.objects.exclude(estado='').values_list('estado',flat=True).distinct().order_by('estado'),
        'modo_hojas':modo_hojas})

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def detalle(request,pk):
    equipo=get_object_or_404(Equipo.objects.select_related('laboratorio'),pk=pk)
    pendientes=equipo.traslados.filter(estado='Pendiente').exists()
    tiene_salon=Laboratorio.objects.filter(responsable=request.user).exists()
    motivo_traslado=''
    if pendientes: motivo_traslado='Este equipo ya tiene un traslado pendiente.'
    elif not equipo.laboratorio.responsable_id: motivo_traslado='Primero asigna un responsable al laboratorio de origen.'
    elif equipo.laboratorio.responsable_id == request.user.pk: motivo_traslado='Este equipo pertenece a tu propio laboratorio.'
    elif not tiene_salon: motivo_traslado='Un administrador debe asignarte un laboratorio de destino.'
    # Show the equipment life-cycle, omitting requester personal data from general readers.
    history=equipo.mantenimiento_set.select_related('tecnico').order_by(F('fecha').desc(nulls_last=True),'-id')
    return render(request,'detalle.html',{'equipo':equipo,'mantenimientos':history,
        'puede_editar_inventario':puede_editar(request.user,equipo),
        'puede_pedir_traslado':not motivo_traslado,
        'motivo_traslado':motivo_traslado,
        'solicitudes':solicitudes_visibles(request.user).filter(equipo=equipo).order_by('-id')})

@login_required
@permission_required('lab.add_equipo',raise_exception=True)
def nuevo_equipo(request):
    form=EquipoForm(request.POST or None)
    if not request.user.is_superuser:
        form.fields['laboratorio'].queryset=Laboratorio.objects.filter(responsable=request.user)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            obj=form.save(); audit(request.user,'Crear equipo',obj)
        messages.success(request,'Equipo creado.'); return redirect('detalle',pk=obj.pk)
    return render(request,'form.html',{'form':form,'titulo':'Nuevo equipo'})

@login_required
@permission_required('lab.change_equipo',raise_exception=True)
def editar_equipo(request,pk):
    equipo=get_object_or_404(Equipo,pk=pk); before=snapshot(equipo)
    exigir_edicion(request.user,equipo)
    form=EquipoForm(request.POST or None,instance=equipo)
    form.fields['laboratorio'].disabled=True
    if request.method=='POST' and form.is_valid():
        data={k:v for k,v in form.cleaned_data.items() if k!='version'}
        with transaction.atomic():
            exigir_edicion(request.user,Equipo.objects.select_for_update().get(pk=pk))
            if Equipo.objects.filter(pk=pk,version=form.cleaned_data['version']).update(**data,version=F('version')+1):
                equipo.refresh_from_db(); audit(request.user,'Editar equipo',equipo,before)
                messages.success(request,'Equipo actualizado.'); return redirect('detalle',pk=pk)
        form.add_error(None,'Otro usuario modificó el equipo. Recarga la página antes de guardar.')
    return render(request,'form.html',{'form':form,'titulo':'Editar equipo'})

@login_required
@permission_required('lab.change_equipo',raise_exception=True)
def editar_hoja(request,pk):
    equipo=get_object_or_404(Equipo,pk=pk)
    exigir_edicion(request.user,equipo)
    form=HojaVidaForm(request.POST or None,equipo=equipo)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            exigir_edicion(request.user,Equipo.objects.select_for_update().get(pk=pk))
            before=snapshot(equipo)
            updated=Equipo.objects.filter(pk=pk,version=form.cleaned_data['version']).update(datos_hoja_vida=form.datos(equipo.datos_hoja_vida),version=F('version')+1)
            if updated:
                equipo.refresh_from_db(); audit(request.user,'Editar hoja de vida',equipo,before)
                messages.success(request,'Hoja de vida actualizada.'); return redirect('detalle',pk=pk)
        form.add_error(None,'Otro usuario modificó el equipo. Recarga la página antes de guardar.')
    return render(request,'form.html',{'form':form,'titulo':'Datos de la hoja de vida'})

@login_required
@permission_required('lab.change_equipo',raise_exception=True)
def cambiar_foto(request,pk):
    equipo=get_object_or_404(Equipo,pk=pk); form=FotoForm(request.POST or None,request.FILES or None)
    exigir_edicion(request.user,equipo)
    if request.method=='POST' and form.is_valid():
        image=Image.open(form.cleaned_data['foto']); image.load(); image=image.convert('RGB'); image.thumbnail((1800,1800))
        data=BytesIO(); image.save(data,format='JPEG',quality=90)
        before=snapshot(equipo)
        with transaction.atomic():
            equipo=Equipo.objects.select_for_update().get(pk=pk)
            exigir_edicion(request.user,equipo)
            equipo.foto.save(f'{uuid4().hex}.jpg',ContentFile(data.getvalue()),save=False)
            equipo.version+=1; equipo.save(update_fields=['foto','version']); audit(request.user,'Cambiar foto',equipo,before)
        messages.success(request,'Fotografía actualizada.'); return redirect('detalle',pk=pk)
    return render(request,'form.html',{'form':form,'titulo':'Cambiar fotografía'})

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def foto(request,pk):
    from .legacy_photo import FotoService
    eq=get_object_or_404(Equipo,pk=pk)
    if eq.foto:
        try: return FileResponse(eq.foto.open('rb'),content_type='image/jpeg')
        except OSError: raise Http404
    path=FotoService().obtener_foto(eq.marca,eq.modelo)
    if not path: raise Http404
    return FileResponse(open(path,'rb'))

@login_required
def solicitudes(request):
    qs=solicitudes_visibles(request.user)
    state=request.GET.get('estado','')
    if state: qs=qs.filter(estado=state)
    q=request.GET.get('q','')
    if q: qs=qs.filter(Q(codigo_legacy__icontains=q)|Q(descripcion__icontains=q)|Q(equipo__placa__icontains=q)|Q(equipo__descripcion__icontains=q)|Q(nombre_solicitante__icontains=q))
    return render(request,'solicitudes.html',{'page':paginate(request,qs.order_by('-id')),'estados':Solicitud.ESTADOS})

@login_required
@permission_required('lab.add_solicitud',raise_exception=True)
def nueva_solicitud(request):
    initial={'equipo':request.GET.get('equipo')}
    form=SolicitudForm(request.POST or None,initial=initial)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            obj=form.save(commit=False); obj.solicitante=request.user; obj.save(); audit(request.user,'Crear solicitud',obj)
        messages.success(request,f'Solicitud {obj.codigo} creada.'); return redirect('detalle_solicitud',pk=obj.pk)
    return render(request,'form.html',{'form':form,'titulo':'Nueva solicitud'})

@login_required
def detalle_solicitud(request,pk):
    obj=get_object_or_404(solicitudes_visibles(request.user),pk=pk)
    return render(request,'solicitud_detalle.html',{'solicitud':obj,
        'cancelar':CancelarForm(initial={'version':obj.version}), 'mantenimientos':obj.mantenimiento_set.all(),
        'puede_eliminar':puede_eliminar_solicitud(request.user,obj)})

def puede_eliminar_solicitud(user,obj):
    return user.has_perm('lab.delete_solicitud') or user.has_perm('lab.change_solicitud') or obj.solicitante_id==user.pk

@login_required
@require_POST
def actualizar_solicitante(request,pk):
    from django import forms
    nombre_field=forms.CharField(max_length=200)
    with transaction.atomic():
        obj=get_object_or_404(Solicitud.objects.select_for_update(),pk=pk)
        if not puede_eliminar_solicitud(request.user,obj): raise PermissionDenied
        try: nombre=nombre_field.clean(request.POST.get('nombre_solicitante'))
        except forms.ValidationError:
            messages.error(request,'Escribe el nombre del solicitante (máximo 200 caracteres).')
            return redirect('detalle_solicitud',pk=pk)
        if request.POST.get('version')!=str(obj.version):
            messages.error(request,'La solicitud cambió. Recarga el detalle antes de corregir el solicitante.')
        else:
            before=snapshot(obj)
            obj.nombre_solicitante=nombre
            obj.version+=1
            obj.save(update_fields=['nombre_solicitante','version'])
            audit(request.user,'Corregir solicitante',obj,before)
            messages.success(request,'Nombre del solicitante actualizado.')
    return redirect('detalle_solicitud',pk=pk)

@login_required
def eliminar_solicitud(request,pk):
    obj=get_object_or_404(Solicitud,pk=pk)
    if not puede_eliminar_solicitud(request.user,obj): raise PermissionDenied
    if request.method=='POST':
        with transaction.atomic():
            obj=get_object_or_404(Solicitud.objects.select_for_update(),pk=pk)
            if not puede_eliminar_solicitud(request.user,obj): raise PermissionDenied
            if request.POST.get('confirmar')!='si' or request.POST.get('version')!=str(obj.version):
                messages.error(request,'Confirma la eliminación. Si la solicitud cambió, revisa su información nuevamente.')
                return redirect('eliminar_solicitud',pk=pk)
            codigo=obj.codigo
            for mantenimiento in obj.mantenimiento_set.select_for_update().all():
                before=snapshot(mantenimiento)
                mantenimiento.datos_legacy={**mantenimiento.datos_legacy,'solicitud_eliminada':snapshot(obj),'codigo_solicitud':codigo}
                mantenimiento.solicitud=None
                mantenimiento.version+=1
                mantenimiento.save(update_fields=['solicitud','datos_legacy','version'])
                audit(request.user,'Conservar mantenimiento al eliminar solicitud',mantenimiento,before)
            audit(request.user,'Eliminar solicitud',obj,detail={'codigo':codigo,'antes':snapshot(obj)})
            obj.delete()
        messages.success(request,f'Solicitud {codigo} eliminada. Sus mantenimientos registrados se conservaron.')
        return redirect('solicitudes')
    return render(request,'eliminar_solicitud.html',{'solicitud':obj,'total_mantenimientos':obj.mantenimiento_set.count()})

@login_required
@permission_required('lab.change_solicitud',raise_exception=True)
@require_POST
def asignar_solicitud(request,pk):
    messages.info(request,'La asignación se realiza al pulsar Realizar mantenimiento.')
    return redirect('detalle_solicitud',pk=pk)

@login_required
@require_POST
def realizar_mantenimiento(request,pk):
    with transaction.atomic():
        obj=get_object_or_404(Solicitud.objects.select_for_update(),pk=pk)
        if obj.estado in ('Cerrada','Cancelada'):
            messages.error(request,'Esta solicitud ya no está disponible.')
        elif obj.tecnico_id and obj.tecnico_id != request.user.pk:
            messages.info(request,'Otro usuario ya está realizando este mantenimiento.')
        else:
            if obj.tecnico_id is None or obj.estado != 'Asignada':
                before=snapshot(obj)
                obj.tecnico=request.user; obj.estado='Asignada'; obj.version+=1; obj.save()
                audit(request.user,'Iniciar mantenimiento',obj,before)
            return redirect(reverse('nuevo_mantenimiento')+'?solicitud='+str(obj.pk))
    return redirect('detalle_solicitud',pk=pk)

@login_required
@require_POST
def cancelar_solicitud(request,pk):
    form=CancelarForm(request.POST)
    with transaction.atomic():
        obj=get_object_or_404(solicitudes_visibles(request.user).select_for_update(of=('self',)),pk=pk)
        if not request.user.has_perm('lab.change_solicitud') and obj.solicitante_id!=request.user.pk: raise PermissionDenied
        if form.is_valid() and obj.estado not in ('Cerrada','Cancelada') and obj.version==form.cleaned_data['version']:
            before=snapshot(obj); obj.estado='Cancelada'; obj.motivo_cancelacion=form.cleaned_data['motivo']; obj.version+=1; obj.save()
            audit(request.user,'Cancelar solicitud',obj,before); messages.success(request,'Solicitud cancelada.')
        else: messages.error(request,'Indica un motivo y verifica que la solicitud siga abierta.')
    return redirect('detalle_solicitud',pk=pk)

@login_required
@require_POST
def liberar_mantenimiento(request,pk):
    with transaction.atomic():
        obj=get_object_or_404(Solicitud.objects.select_for_update(),pk=pk)
        if obj.tecnico_id != request.user.pk:
            raise PermissionDenied
        if obj.estado != 'Asignada':
            messages.info(request,'Esta solicitud ya no tiene un mantenimiento en curso.')
        else:
            before=snapshot(obj)
            obj.tecnico=None
            obj.estado='Pendiente'
            obj.version+=1
            obj.save(update_fields=['tecnico','estado','version'])
            audit(request.user,'Liberar mantenimiento',obj,before)
            messages.success(request,f'{obj.codigo} liberada. Ya está disponible para todos.')
    return redirect('solicitudes')

@login_required
def nuevo_mantenimiento(request):
    initial={'tipo':'MIPV' if request.GET.get('preventivo') else 'MIC','equipo':request.GET.get('equipo')}
    sol=None
    solicitud_id=request.GET.get('solicitud') or request.POST.get('solicitud','')
    if solicitud_id.isdigit():
        sol=get_object_or_404(solicitudes_visibles(request.user),pk=solicitud_id)
        if sol.tecnico_id != request.user.pk or sol.estado != 'Asignada':
            messages.info(request,'Abre la solicitud y pulsa Realizar mantenimiento para comenzar.')
            return redirect('detalle_solicitud',pk=sol.pk)
        initial.update({'solicitud':sol.pk,'equipo':sol.equipo_id,'tipo':sol.tipo})
    if sol is None:
        form=SolicitarMantenimientoForm(request.POST if request.method=='POST' else None,initial=initial)
        if request.method=='POST' and form.is_valid():
            with transaction.atomic():
                obj=form.save(commit=False)
                obj.solicitante=request.user
                obj.fecha_reporte=timezone.localdate()
                obj.hora_reporte=timezone.localtime().time().replace(microsecond=0)
                obj.estado='Pendiente'
                obj.tecnico=None
                obj.save()
                audit(request.user,'Solicitar mantenimiento',obj)
            messages.success(request,f'{obj.codigo} registrada. Está disponible para que cualquier usuario realice el mantenimiento.')
            return redirect('detalle_solicitud',pk=obj.pk)
        return render(request,'form.html',{'form':form,'numero_automatico':True,'titulo':'Solicitar mantenimiento'})
    data=request.POST.copy() if request.method=='POST' else None
    if data is not None and sol:
        data.setdefault('fecha',timezone.localdate().isoformat())
    form=MantenimientoForm(data,initial=initial,solicitud_contexto=sol)
    qs=Solicitud.objects.filter(estado='Asignada',tecnico=request.user)
    form.fields['solicitud'].queryset=qs
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            obj=form.save(commit=False); obj.tecnico=request.user
            if obj.solicitud_id:
                sol=Solicitud.objects.select_for_update().get(pk=obj.solicitud_id)
                if sol.estado in ('Cerrada','Cancelada'):
                    form.add_error(None,'La solicitud ya fue finalizada o cancelada.')
                elif sol.tecnico_id!=request.user.pk: raise PermissionDenied
                elif sol.equipo_id and sol.equipo_id != obj.equipo_id:
                    form.add_error('equipo','La solicitud pertenece a otro equipo.')
                else:
                    before=snapshot(sol)
                    if sol.equipo_id is None: sol.equipo=obj.equipo
                    if obj.equipo_id is None: obj.datos_legacy=dict(sol.datos_legacy)
                    obj.save(); sol.estado='Cerrada'; sol.version+=1; sol.save()
                    audit(request.user,'Finalizar solicitud',sol,before); audit(request.user,'Registrar mantenimiento',obj)
                    messages.success(request,'Mantenimiento registrado y solicitud finalizada.'); return redirect('detalle_mantenimiento',pk=obj.pk)
    return render(request,'mantenimiento_rapido.html' if sol else 'form.html',{'form':form,'solicitud':sol,'numero_automatico':sol is None,'titulo':'Mantenimiento preventivo' if request.GET.get('preventivo') else 'Registrar mantenimiento'})

@login_required
@permission_required('lab.add_mantenimiento',raise_exception=True)
def mantenimiento_lote(request):
    from .forms import MantenimientoLoteForm
    laboratorio_id = request.POST.get('laboratorio') if request.method == 'POST' else request.GET.get('laboratorio')
    form = MantenimientoLoteForm(request.POST if request.method == 'POST' else None, laboratorio_id=laboratorio_id, initial={'laboratorio':laboratorio_id})
    if request.method == 'POST' and form.is_valid():
        data = form.cleaned_data
        ids = [e.pk for e in data['equipos']]
        with transaction.atomic():
            equipos = list(Equipo.objects.select_for_update().filter(pk__in=ids,laboratorio=data['laboratorio']).order_by('pk'))
            if len(equipos) != len(ids):
                form.add_error('equipos','La ubicación de un equipo cambió. Vuelve a seleccionar los equipos.')
            else:
                lote = uuid4()
                for equipo in equipos:
                    obj = Mantenimiento.objects.create(equipo=equipo,tecnico=request.user,lote=lote,cantidad_equipos=len(equipos),segundos_totales=data['segundos_totales'],**{key:data[key] for key in ['fecha','hora_inicio','hora_fin','tipo','especificaciones','diagnostico','observaciones','estado']})
                    audit(request.user,'Registrar mantenimiento por lote',obj)
                messages.success(request,f'Se crearon {len(equipos)} reportes individuales; {obj.minutos_asignados:.2f} minutos por equipo.')
                return redirect('historial')
    return render(request,'mantenimiento_lote.html',{'form':form,'laboratorios':Laboratorio.objects.order_by('nombre'),'laboratorio_id':str(laboratorio_id or '')})

def history_filter(request):
    qs=mantenimientos_visibles(request.user)
    if request.GET.get('laboratorio','').isdigit(): qs=qs.filter(equipo__laboratorio_id=request.GET['laboratorio'])
    if request.GET.get('tipo'): qs=qs.filter(tipo=request.GET['tipo'])
    for name,lookup in [('desde','fecha__gte'),('hasta','fecha__lte')]:
        from .importing import parse_date
        value=parse_date(request.GET.get(name))
        if value: qs=qs.filter(**{lookup:value})
    q=request.GET.get('q','')
    if q: qs=qs.filter(Q(equipo__descripcion__icontains=q)|Q(equipo__placa__icontains=q)|Q(responsable_legacy__icontains=q)|Q(diagnostico__icontains=q))
    return qs.order_by(F('fecha').desc(nulls_last=True),'-id')

@login_required
@permission_required('lab.view_mantenimiento',raise_exception=True)
def historial(request):
    return render(request,'historial.html',{'page':paginate(request,history_filter(request)),
        'laboratorios':Laboratorio.objects.order_by('nombre'),'tipos':Mantenimiento.objects.values_list('tipo',flat=True).distinct().order_by('tipo')})

@login_required
def detalle_mantenimiento(request,pk):
    qs=mantenimientos_visibles(request.user) if request.user.has_perm('lab.view_mantenimiento') else Mantenimiento.objects.filter(Q(tecnico=request.user)|Q(solicitud__in=solicitudes_visibles(request.user)))
    obj=get_object_or_404(qs,pk=pk)
    return render(request,'mantenimiento_detalle.html',{'mantenimiento':obj})

@login_required
@permission_required('lab.change_mantenimiento',raise_exception=True)
def editar_mantenimiento(request,pk):
    from django import forms
    obj=get_object_or_404(Mantenimiento,pk=pk); before=snapshot(obj)
    form=MantenimientoForm(request.POST or None,instance=obj)
    form.fields['version']=forms.IntegerField(widget=forms.HiddenInput,initial=obj.version)
    form.fields['solicitud'].disabled=True
    if obj.equipo_id: form.fields['equipo'].disabled=True
    if request.method=='POST' and form.is_valid():
        values={k:v for k,v in form.cleaned_data.items() if k!='version'}
        with transaction.atomic():
            if Mantenimiento.objects.filter(pk=pk,version=form.cleaned_data['version']).update(**values,version=F('version')+1):
                obj.refresh_from_db(); audit(request.user,'Editar mantenimiento',obj,before)
                messages.success(request,'Mantenimiento actualizado.'); return redirect('detalle_mantenimiento',pk=pk)
        form.add_error(None,'Otra persona modificó el mantenimiento. Recarga antes de guardar.')
    return render(request,'form.html',{'form':form,'titulo':'Editar mantenimiento'})

@login_required
@permission_required('lab.view_mantenimiento',raise_exception=True)
def estadisticas(request):
    return render(request,'estadisticas.html',resumen_estadisticas(request))

def resumen_estadisticas(request):
    qs=history_filter(request)
    return {'total':qs.count(),'tipos':qs.values('tipo').annotate(total=Count('id')).order_by('-total'),
        'laboratorios':qs.values('equipo__laboratorio__nombre').annotate(total=Count('id')).order_by('-total'),
        'estados':solicitudes_visibles(request.user).values('estado').annotate(total=Count('id')).order_by('-total'),
        'sin_vinculo':qs.filter(equipo__isnull=True).count()}

@login_required
@permission_required('lab.view_mantenimiento',raise_exception=True)
def exportar_estadisticas(request):
    from openpyxl.styles import Font,PatternFill
    from openpyxl.chart import BarChart,Reference
    resumen=resumen_estadisticas(request)
    wb=Workbook();wb.remove(wb.active)
    def sheet(name,headers,rows):
        ws=wb.create_sheet(name);ws.append(headers)
        for row in rows:
            ws.append(list(row))
            for cell in ws[ws.max_row]:
                if isinstance(cell.value,str):cell.data_type='s'
        for cell in ws[1]:
            cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='B1222B')
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width=min(60,max(22,len(str(column[0].value))+4))
        return ws
    filters=[('Generado',timezone.localtime().strftime('%Y-%m-%d %H:%M')),('Intervenciones del filtro',resumen['total']),('Equipos sin vincular',resumen['sin_vinculo'])]
    laboratorio=request.GET.get('laboratorio','')
    nombre_lab=Laboratorio.objects.filter(pk=int(laboratorio)).values_list('nombre',flat=True).first() if laboratorio.isdigit() else None
    filters.extend([('Laboratorio',nombre_lab or 'Todos'),('Tipo',request.GET.get('tipo') or 'Todos'),('Desde',request.GET.get('desde') or 'Sin límite'),('Hasta',request.GET.get('hasta') or 'Sin límite'),('Búsqueda',request.GET.get('q') or 'Sin filtro'),('Solicitudes','Todos los períodos; no aplica el filtro de intervenciones')])
    sheet('Resumen',['Indicador o filtro','Valor'],filters)
    types=sheet('Por tipo',['Tipo de mantenimiento','Intervenciones'],((t['tipo'] or 'Sin clasificar',t['total']) for t in resumen['tipos']))
    if types.max_row>1:
        chart=BarChart();chart.title='Intervenciones por tipo';chart.y_axis.title='Intervenciones';chart.x_axis.title='Tipo'
        chart.add_data(Reference(types,min_col=2,min_row=1,max_row=types.max_row),titles_from_data=True)
        chart.set_categories(Reference(types,min_col=1,min_row=2,max_row=types.max_row));types.add_chart(chart,'D2')
    sheet('Por laboratorio',['Laboratorio','Intervenciones'],((l['equipo__laboratorio__nombre'] or 'Histórico sin vincular',l['total']) for l in resumen['laboratorios']))
    labels=dict(Solicitud.ESTADOS)
    sheet('Solicitudes todos los períodos',['Estado','Solicitudes'],((labels.get(s['estado'],s['estado']),s['total']) for s in resumen['estados']))
    sheet('Intervenciones',['Solicitud','Equipo','Placa','Laboratorio','Tipo','Fecha','Responsable','Diagnóstico','Trabajo realizado','Estado','Observaciones'],
        ((m.solicitud.codigo if m.solicitud else m.datos_legacy.get('codigo_solicitud',''),m.equipo_nombre,m.equipo.placa if m.equipo_id else m.datos_legacy.get('placa',''),str(m.equipo.laboratorio) if m.equipo_id else m.datos_legacy.get('laboratorio',''),m.tipo,m.fecha,m.responsable_legacy or m.tecnico.get_full_name() or m.tecnico.username,m.diagnostico,m.especificaciones,m.estado,m.observaciones) for m in history_filter(request).iterator()))
    output=BytesIO();wb.save(output);wb.close();output.seek(0)
    return FileResponse(output,as_attachment=True,filename='Reporte_estadisticas_LabManager.xlsx')

def excel_response(headers, rows, filename):
    wb=Workbook(); ws=wb.active; ws.title='Datos'
    ws.append(headers)
    for row in rows:
        ws.append(list(row))
        # Keep user-supplied text as text, including formula-like strings.
        for cell in ws[ws.max_row]:
            if isinstance(cell.value,str): cell.data_type='s'
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    for column in ws.columns: ws.column_dimensions[column[0].column_letter].width=min(60,max(18,len(str(column[0].value))+3))
    data=BytesIO(); wb.save(data); wb.close(); data.seek(0)
    return FileResponse(data,as_attachment=True,filename=filename)

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def exportar_inventario(request):
    qs=inventory(request)
    headers=['Placa UD','N. Interno','Serial','Descripción','Marca','Modelo','Estado','Laboratorio','Funcionario','Inventario físico','ARKA','ERP','Observaciones']
    rows=((e.placa,e.numero_interno,e.serial,e.descripcion,e.marca,e.modelo,e.estado,str(e.laboratorio),e.funcionario,e.inventario_fisico,e.arka,e.erp,e.observaciones) for e in qs.iterator())
    return excel_response(headers,rows,'Inventario_LabManager.xlsx')

@login_required
@permission_required('lab.view_mantenimiento',raise_exception=True)
def exportar_mantenimientos(request):
    headers=['Código','Equipo','Placa','Interno','Laboratorio','Tipo','Fecha','Técnico','Empresa','Garantía','Diagnóstico','Mantenimiento realizado','Estado','Observaciones','Repuestos','Enlace','Hora inicio','Hora fin','Minutos asignados','Sesión']
    rows=((m.solicitud.codigo if m.solicitud else '',m.equipo_nombre,m.equipo.placa if m.equipo else m.datos_legacy.get('placa'),m.equipo.numero_interno if m.equipo else m.datos_legacy.get('interno'),str(m.equipo.laboratorio) if m.equipo else m.datos_legacy.get('laboratorio'),m.tipo,m.fecha,m.responsable_legacy or m.tecnico.get_full_name() or m.tecnico.username,m.empresa,m.garantia,m.diagnostico,m.especificaciones,m.estado,m.observaciones,m.repuestos,m.enlace_repuesto,m.hora_inicio,m.hora_fin,m.minutos_asignados,str(m.lote) if m.lote else None) for m in history_filter(request).iterator())
    return excel_response(headers,rows,'Reporte_mantenimientos.xlsx')

@login_required
@permission_required('lab.change_solicitud',raise_exception=True)
def exportar_reporte(request):
    """Preserve the desktop's A:AA layout and companion institutional worksheets."""
    from openpyxl import load_workbook
    path=settings.RESOURCES_ROOT/'mantenimientos/REPORTE_MANTENIMIENTOS.xlsx'
    wb=load_workbook(path) if path.exists() else Workbook()
    if 'Datos' not in wb.sheetnames: wb.active.title='Datos'
    ws=wb['Datos']
    headers=['CONSECUTIVO','Nombre1','Documento de Identidad','TIPO DE MANTENIMIENTO','Fecha del reporte','Hora de ingreso','Nombre del Equipo','Marca','Placa del equipo','Número INTERNO','Laboratorio de ubicación','Asignatura','Número de banco','Descripción del daño','observacion','Técnico','FECHA DE REALIZACIÓN','DATOS EMPRESA CONTRATADA','TIEMPO DE GARANTÍA','Diagnóstico','ESPECIFICACIONES DEL MANTENIMIENTO REALIZADO','ESTADO','REPUESTO SOLICITADO','Link del repuesto','Estado solicitud','Celular','Tipo solicitante']
    if ws.max_row>3: ws.delete_rows(4,ws.max_row-3)
    for col,name in enumerate(headers,1): ws.cell(3,col,name)
    for s in Solicitud.objects.select_related('equipo','equipo__laboratorio','tecnico').prefetch_related('mantenimiento_set').order_by('id'):
        interventions=list(s.mantenimiento_set.all()) or [None]
        for m in interventions:
            eq=s.equipo; data=s.datos_legacy
            row=[s.codigo,s.nombre_solicitante,s.documento,s.tipo,s.fecha_reporte,s.hora_reporte,
                eq.descripcion if eq else data.get('equipo'),eq.marca if eq else data.get('marca'),eq.placa if eq else data.get('placa'),eq.numero_interno if eq else data.get('interno'),str(eq.laboratorio) if eq else data.get('laboratorio'),s.asignatura,s.banco,s.descripcion,s.observaciones,
                (m.responsable_legacy or m.tecnico.get_full_name() or m.tecnico.username) if m else '',m.fecha if m else '',m.empresa if m else '',m.garantia if m else '',m.diagnostico if m else '',m.especificaciones if m else '',m.estado if m else '',m.repuestos if m else '',m.enlace_repuesto if m else '',s.get_estado_display(),s.celular,s.tipo_solicitante]
            ws.append(row)
            for cell in ws[ws.max_row]:
                if isinstance(cell.value,str): cell.data_type='s'
    for m in Mantenimiento.objects.filter(solicitud__isnull=True).select_related('equipo','equipo__laboratorio','tecnico').order_by('id'):
        eq=m.equipo; data=m.datos_legacy
        ws.append([f'M-{m.pk:06d}',m.tecnico.get_full_name() or m.tecnico.username,'',m.tipo,m.fecha,'',
            eq.descripcion if eq else data.get('equipo'),eq.marca if eq else data.get('marca'),eq.placa if eq else data.get('placa'),eq.numero_interno if eq else data.get('interno'),str(eq.laboratorio) if eq else data.get('laboratorio'),'','','Mantenimiento independiente','\n'.join(filter(None,[m.observaciones,m.resumen_tiempo])),
            m.responsable_legacy or m.tecnico.get_full_name() or m.tecnico.username,m.fecha,m.empresa,m.garantia,m.diagnostico,m.especificaciones,m.estado,m.repuestos,m.enlace_repuesto,'Finalizada','','Técnico'])
        for cell in ws[ws.max_row]:
            if isinstance(cell.value,str): cell.data_type='s'
    ws.freeze_panes='A4'
    output=BytesIO(); wb.save(output); wb.close(); output.seek(0)
    return FileResponse(output,as_attachment=True,filename='REPORTE_MANTENIMIENTOS.xlsx')

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
@require_POST
def documento(request,pk,formato):
    from .documents import generar
    if formato not in ('xlsx','pdf'): raise Http404
    equipo=get_object_or_404(Equipo,pk=pk)
    try: data=generar(equipo,formato)
    except (RuntimeError,OSError) as exc: return render(request,'error.html',{'error':str(exc)},status=503)
    audit(request.user,'Generar '+formato,equipo,detail={'formato':formato})
    response=FileResponse(data,as_attachment=not request.POST.get('ver'),filename=f'HV_{pk}.{formato}')
    return response

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
@require_POST
def exportar_lote(request):
    from .jobs import launch
    formato=request.POST.get('formato','xlsx')
    if formato not in ('xlsx','pdf'): raise Http404
    ids=list(inventory(request).values_list('id',flat=True))
    if not ids:
        messages.error(request,'El filtro no contiene equipos.'); return redirect('equipos')
    obj=TrabajoDocumento.objects.create(usuario=request.user,formato=formato,equipos=ids)
    launch(obj.pk)
    messages.success(request,f'Exportación iniciada para {len(ids)} equipos.'); return redirect('trabajos')

@login_required
def trabajos(request):
    qs=TrabajoDocumento.objects.filter(usuario=request.user).order_by('-id')
    return render(request,'trabajos.html',{'page':paginate(request,qs)})

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def descargar_trabajo(request,pk):
    obj=get_object_or_404(TrabajoDocumento,pk=pk,usuario=request.user)
    if not obj.archivo or obj.estado not in ('Completado','Parcial'): raise Http404
    return FileResponse(obj.archivo.open('rb'),as_attachment=True,filename=f'HojasVida_{pk}.zip')

@login_required
@permission_required('lab.importar_datos',raise_exception=True)
def importacion(request):
    from .importing import importar
    form=ImportarForm(request.POST or None,request.FILES or None); report=None
    if request.method=='POST' and form.is_valid():
        try:
            uploaded=form.cleaned_data.get('archivo')
            with TemporaryDirectory(prefix='lab-import-') as directory:
                path=None
                if uploaded:
                    safe=Path(uploaded.name.replace('\\','/')).name
                    path=Path(directory)/safe
                    with path.open('wb') as stream:
                        for chunk in uploaded.chunks(): stream.write(chunk)
                    with zipfile.ZipFile(path) as archive:
                        if sum(i.file_size for i in archive.infolist())>100*1024*1024: raise ValueError('El Excel descomprimido supera 100 MB.')
                report=importar(request.user,apply=form.cleaned_data['accion']=='aplicar',inventory_path=path)
            messages.success(request,'Importación aplicada.' if report['aplicado'] else 'Simulación terminada: los cambios no se guardaron.')
        except (ValueError,KeyError,OSError,zipfile.BadZipFile) as exc: form.add_error(None,str(exc))
    return render(request,'importacion.html',{'form':form,'report':report,'pendientes':RegistroLegacy.objects.filter(estado='Pendiente').count()})

@login_required
@permission_required('lab.importar_datos',raise_exception=True)
def registros(request):
    qs=RegistroLegacy.objects.select_related('equipo')
    if request.GET.get('estado','Pendiente'): qs=qs.filter(estado=request.GET.get('estado','Pendiente'))
    if request.GET.get('q'): qs=qs.filter(Q(archivo__icontains=request.GET['q'])|Q(motivo__icontains=request.GET['q']))
    return render(request,'registros.html',{'page':paginate(request,qs)})

@login_required
@permission_required('lab.importar_datos',raise_exception=True)
def conciliar(request,pk):
    record=get_object_or_404(RegistroLegacy,pk=pk); form=ConciliarForm(request.POST or None,initial={'equipo':record.equipo_id})
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            record=RegistroLegacy.objects.select_for_update().get(pk=pk)
            before=snapshot(record); eq=Equipo.objects.select_for_update().get(pk=form.cleaned_data['equipo'].pk)
            if record.categoria=='hoja_vida':
                eq.datos_hoja_vida={**record.datos,**eq.datos_hoja_vida}; eq.version+=1; eq.save(update_fields=['datos_hoja_vida','version'])
            elif record.categoria=='reporte':
                Solicitud.objects.filter(origen=record.origen).update(equipo=eq,version=F('version')+1)
                Mantenimiento.objects.filter(origen=record.origen).update(equipo=eq,version=F('version')+1)
            elif record.categoria=='inventario' and not record.equipo_id:
                eq.datos_origen=record.datos
                if not eq.origen: eq.origen=record.origen
                eq.version+=1; eq.save(update_fields=['datos_origen','origen','version'])
            else:
                messages.error(request,'Este registro de inventario ya conserva su identidad original; no se fusiona automáticamente.')
                return redirect('conciliar',pk=pk)
            record.equipo=eq; record.estado='Revisada'; record.motivo=form.cleaned_data['nota']; record.save()
            audit(request.user,'Conciliar registro',record,before)
        messages.success(request,'Vinculación guardada.'); return redirect('registros')
    return render(request,'conciliar.html',{'registro':record,'form':form})

@login_required
@permission_required('lab.view_laboratorio',raise_exception=True)
def laboratorios(request):
    return render(request,'laboratorios.html',{'laboratorios':Laboratorio.objects.annotate(total=Count('equipo')).order_by('nombre')})

@login_required
@permission_required('lab.add_laboratorio',raise_exception=True)
def nuevo_laboratorio(request):
    form=LaboratorioForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic(): obj=form.save(); audit(request.user,'Crear laboratorio',obj)
        return redirect('laboratorios')
    return render(request,'form.html',{'form':form,'titulo':'Nuevo laboratorio'})

@login_required
def perfil(request):
    before=snapshot(request.user)
    appearance=AparienciaPerfil.objects.filter(usuario=request.user).first() or AparienciaPerfil(usuario=request.user)
    form=PerfilForm(request.POST if request.method=='POST' else None,instance=request.user)
    preferences=AparienciaForm(request.POST if request.method=='POST' else None,request.FILES or None,instance=appearance)
    valid_user=form.is_valid() if request.method=='POST' else False
    valid_appearance=preferences.is_valid() if request.method=='POST' else False
    if request.method=='POST' and valid_user and valid_appearance:
        with transaction.atomic():
            obj=form.save(); audit(request.user,'Editar perfil',obj,before)
            appearance=preferences.save(commit=False)
            if request.POST.get('restaurar')=='si':
                appearance.primario='#d82935';appearance.secundario='#f2cb62';appearance.fondo='#f8f6f3'
            for key,size in [('avatar',(400,400)),('portada',(1800,700))]:
                photo=preferences.cleaned_data.get(key)
                if photo and hasattr(photo,'content_type'):
                    from PIL import ImageOps
                    photo.seek(0)
                    picture=ImageOps.exif_transpose(Image.open(photo)).convert('RGB')
                    picture.thumbnail(size)
                    output=BytesIO();picture.save(output,format='JPEG',quality=88)
                    getattr(appearance,key).save(f'{uuid4().hex}.jpg',ContentFile(output.getvalue()),save=False)
            appearance.save()
            audit(request.user,'Personalizar apariencia',appearance)
        messages.success(request,'Perfil actualizado.'); return redirect('perfil')
    return render(request,'perfil.html',{'form':form,'preferencias':preferences})

@login_required
def foto_perfil(request,tipo):
    if tipo not in ('avatar','portada'): raise Http404
    appearance=get_object_or_404(AparienciaPerfil,usuario=request.user)
    photo=getattr(appearance,tipo)
    if not photo: raise Http404
    try: response=FileResponse(photo.open('rb'),content_type='image/jpeg')
    except OSError: raise Http404
    response['Cache-Control']='private, no-store'
    response['X-Content-Type-Options']='nosniff'
    return response

@login_required
@permission_required('auth.view_user',raise_exception=True)
def usuarios(request):
    return render(request,'usuarios.html',{'usuarios':get_user_model().objects.prefetch_related('groups').order_by('username')})

@login_required
@permission_required('auth.change_user',raise_exception=True)
def editar_usuario(request,pk):
    obj=get_object_or_404(get_user_model(),pk=pk)
    before=snapshot(obj)
    if obj.is_superuser and not request.user.is_superuser: raise PermissionDenied
    form=EditarUsuarioForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        if obj.pk==request.user.pk and not form.cleaned_data['is_active']:
            form.add_error('is_active','No puedes desactivar tu propia cuenta.')
        else:
            with transaction.atomic():
                previous_groups=list(obj.groups.values_list('name',flat=True))
                obj=form.save(); obj.groups.set(form.cleaned_data['grupos'])
                audit(request.user,'Editar usuario',obj,detail={'antes':before,'despues':snapshot(obj),'grupos_antes':previous_groups,'grupos_despues':[g.name for g in obj.groups.all()]})
            messages.success(request,'Usuario y roles actualizados.'); return redirect('usuarios')
    return render(request,'form.html',{'form':form,'titulo':'Editar usuario y roles','usuario_edicion':obj})

@login_required
@permission_required('auth.change_user',raise_exception=True)
def restablecer_password(request,pk):
    from django.contrib.auth.forms import SetPasswordForm
    from django.contrib.auth import update_session_auth_hash
    obj=get_object_or_404(get_user_model(),pk=pk)
    if obj.is_superuser and not request.user.is_superuser: raise PermissionDenied
    form=SetPasswordForm(obj,request.POST or None)
    if request.method=='POST' and form.is_valid():
        form.save()
        if obj.pk==request.user.pk: update_session_auth_hash(request,obj)
        audit(request.user,'Restablecer contraseña',obj,detail={'usuario':obj.username})
        messages.success(request,'Contraseña actualizada.'); return redirect('usuarios')
    return render(request,'form.html',{'form':form,'titulo':'Restablecer contraseña: '+obj.username})

@login_required
@permission_required('auth.add_user',raise_exception=True)
def nuevo_usuario(request):
    form=UsuarioForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            obj=form.save(); obj.groups.set(form.cleaned_data['grupos']); audit(request.user,'Crear usuario',obj)
        messages.success(request,'Usuario creado.'); return redirect('usuarios')
    return render(request,'form.html',{'form':form,'titulo':'Nuevo usuario'})

@login_required
@permission_required('lab.view_auditoria',raise_exception=True)
def auditoria(request):
    qs=Auditoria.objects.select_related('usuario').order_by('-id')
    return render(request,'auditoria.html',{'page':paginate(request,qs)})


@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def traslados(request):
    return render(request,'traslados.html',{'page':paginate(request,traslados_visibles(request.user))})

def traslados_visibles(user):
    qs=Traslado.objects.select_related('equipo','origen','destino','solicitante','aprobador')
    return qs.filter(Q(solicitante=user)|Q(aprobador=user)).order_by('-creado')

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def exportar_traslados(request):
    wb=Workbook()
    ws=wb.active
    ws.title='Traslados'
    ws.append(['Solicitud','Equipo','Placa','Serial','Origen','Destino','Solicitante','Responsable de origen','Estado','Fecha de solicitud','Fecha de respuesta','Justificación','Respuesta'])
    for t in traslados_visibles(request.user).iterator():
        row=[t.pk,t.equipo.descripcion,t.equipo.placa,t.equipo.serial,str(t.origen),str(t.destino),t.solicitante.get_full_name() or t.solicitante.username,t.aprobador.get_full_name() or t.aprobador.username,t.estado,timezone.localtime(t.creado).strftime('%Y-%m-%d %H:%M'),timezone.localtime(t.resuelto).strftime('%Y-%m-%d %H:%M') if t.resuelto else '',t.justificacion,t.respuesta]
        ws.append(row)
        for cell in ws[ws.max_row]:
            if isinstance(cell.value,str): cell.data_type='s'
    ws.freeze_panes='A2'
    ws.auto_filter.ref=ws.dimensions
    from openpyxl.styles import Font, PatternFill
    for cell in ws[1]:
        cell.font=Font(bold=True,color='FFFFFF')
        cell.fill=PatternFill('solid',fgColor='0B3C5D')
    for col in ws.columns: ws.column_dimensions[col[0].column_letter].width=24
    output=BytesIO()
    wb.save(output)
    response=HttpResponse(output.getvalue(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition']='attachment; filename="reporte_traslados.xlsx"'
    return response

@login_required
@permission_required('lab.view_equipo',raise_exception=True)
def pedir_traslado(request,pk):
    from .forms import TrasladoForm
    equipo=get_object_or_404(Equipo.objects.select_related('laboratorio'),pk=pk)
    form=TrasladoForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                obj=pedir(request.user,pk,form.cleaned_data['destino'].pk,form.cleaned_data['justificacion'])
                audit(request.user,'Pedir traslado',obj)
            messages.success(request,'Solicitud enviada al responsable del laboratorio de origen.')
            return redirect('traslados')
        except ValidationError as exc:
            form.add_error(None,exc)
    return render(request,'pedir_traslado.html',{'form':form,'equipo':equipo})

@login_required
@require_POST
def resolver_traslado(request,pk):
    get_object_or_404(Traslado,pk=pk)
    try:
        with transaction.atomic():
            obj=resolver(request.user,pk,request.POST.get('decision'),request.POST.get('respuesta','')[:3000])
            audit(request.user,'Resolver traslado',obj)
        messages.success(request,f'Solicitud {obj.estado.lower()}.')
    except ValidationError as exc:
        messages.error(request,' '.join(exc.messages))
    return redirect('traslados')

@login_required
def alertas_traslado(request):
    return JsonResponse({'pendientes':Traslado.objects.filter(aprobador=request.user,estado='Pendiente').count(), 'solicitudes':solicitudes_visibles(request.user).filter(estado='Pendiente').count()})

@login_required
@permission_required('lab.change_laboratorio',raise_exception=True)
def editar_laboratorio(request,pk):
    obj=get_object_or_404(Laboratorio,pk=pk)
    form=LaboratorioForm(request.POST or None,instance=obj)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked=Laboratorio.objects.select_for_update().get(pk=pk)
            if Traslado.objects.filter(Q(origen=locked)|Q(destino=locked),estado='Pendiente').exists():
                form.add_error(None,'Resuelve los traslados pendientes antes de cambiar el laboratorio.')
            else:
                before=snapshot(locked)
                obj=form.save(); audit(request.user,'Editar laboratorio',obj,before)
                return redirect('laboratorios')
    return render(request,'form.html',{'form':form,'titulo':'Responsable del laboratorio'})
