from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group,Permission
class Command(BaseCommand):
    help='Crear o actualizar grupos de acceso'
    def handle(self,*args,**kwargs):
        roles={'Consulta':['view_equipo','view_laboratorio','view_mantenimiento'],'Solicitante':['view_equipo','view_laboratorio','add_solicitud'],'Tecnico':['add_equipo','change_equipo','view_equipo','view_laboratorio','view_solicitud','add_mantenimiento','view_mantenimiento'],'Coordinador':['view_equipo','add_equipo','change_equipo','view_laboratorio','add_laboratorio','change_laboratorio','view_solicitud','add_solicitud','change_solicitud','add_mantenimiento','view_mantenimiento','change_mantenimiento','importar_datos','view_registrolegacy','change_registrolegacy','view_auditoria']}
        for name,codes in roles.items():
            group,_=Group.objects.get_or_create(name=name)
            group.permissions.set(Permission.objects.filter(content_type__app_label='lab',codename__in=codes))
        group,_=Group.objects.get_or_create(name='Administrador')
        group.permissions.set(Permission.objects.filter(content_type__app_label__in=['lab','auth']))
        self.stdout.write('Roles configurados. Asigne grupos desde /admin/. El acceso al admin requiere is_staff.')
