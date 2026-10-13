from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .models import Equipo, Laboratorio, Traslado

ESTADO_TRASLADO = 'En proceso de traslado'

def puede_editar(user, equipo):
    return (user.is_superuser or equipo.laboratorio.responsable_id == user.pk) and not equipo.traslados.filter(estado='Pendiente').exists()

def exigir_edicion(user, equipo):
    if not puede_editar(user, equipo):
        raise PermissionDenied('Solo el responsable puede editar el inventario y el equipo debe estar libre de traslados pendientes.')

@transaction.atomic
def pedir(user, equipo_id, destino_id, justificacion):
    equipo = Equipo.objects.select_for_update().get(pk=equipo_id)
    labs = {l.pk:l for l in Laboratorio.objects.select_for_update().filter(pk__in=[equipo.laboratorio_id,destino_id]).order_by('pk')}
    origen, destino = labs[equipo.laboratorio_id], labs.get(destino_id)
    if not user.has_perm('lab.view_equipo') or not destino or destino.responsable_id != user.pk:
        raise PermissionDenied('Selecciona un laboratorio del que seas responsable.')
    if origen.pk == destino.pk or origen.responsable_id == user.pk or not origen.responsable_id or not origen.responsable.is_active:
        raise ValidationError('El origen debe pertenecer a otro técnico activo.')
    if equipo.traslados.filter(estado='Pendiente').exists():
        raise ValidationError('Este equipo ya tiene un traslado pendiente.')
    if not justificacion.strip():
        raise ValidationError('Escribe la justificación del traslado.')
    obj = Traslado.objects.create(equipo=equipo, origen=origen, destino=destino, solicitante=user, aprobador=origen.responsable, justificacion=justificacion.strip(), estado_anterior=equipo.estado)
    equipo.estado = ESTADO_TRASLADO
    equipo.version += 1
    equipo.save(update_fields=['estado','version'])
    return obj

@transaction.atomic
def resolver(user, traslado_id, decision, respuesta=''):
    # Todas las operaciones de traslado bloquean primero el equipo.
    equipo_id = Traslado.objects.values_list('equipo_id',flat=True).get(pk=traslado_id)
    equipo = Equipo.objects.select_for_update().get(pk=equipo_id)
    obj = Traslado.objects.select_for_update().get(pk=traslado_id)
    labs = {l.pk:l for l in Laboratorio.objects.select_for_update().filter(pk__in=[obj.origen_id,obj.destino_id]).order_by('pk')}
    if user.pk != obj.aprobador_id or labs[obj.origen_id].responsable_id != user.pk:
        raise PermissionDenied('Solo el responsable del laboratorio de origen puede responder.')
    if obj.estado != 'Pendiente':
        raise ValidationError('Esta solicitud ya fue resuelta.')
    if decision not in ('Aprobado','Rechazado'):
        raise ValidationError('Decisión inválida.')
    if equipo.laboratorio_id != obj.origen_id:
        raise ValidationError('La ubicación del equipo cambió. Revisa la solicitud.')
    if decision == 'Aprobado':
        if labs[obj.destino_id].responsable_id != obj.solicitante_id or not obj.solicitante.is_active:
            raise ValidationError('El responsable del destino cambió o está inactivo.')
        equipo.laboratorio_id = obj.destino_id
    equipo.estado = obj.estado_anterior
    equipo.version += 1
    equipo.save(update_fields=['laboratorio','estado','version'])
    obj.estado, obj.respuesta, obj.resuelto = decision, respuesta.strip(), timezone.now()
    obj.save(update_fields=['estado','respuesta','resuelto'])
    return obj
