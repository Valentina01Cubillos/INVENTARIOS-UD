from django.contrib import admin
from .models import Laboratorio,Equipo,Solicitud,Mantenimiento,Auditoria
from .models import Traslado
from .transfers import puede_editar
from django.db.models import Q
@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ['placa','numero_interno','descripcion','laboratorio','estado']
    search_fields = ['placa','numero_interno','serial','descripcion']
    list_filter = ['laboratorio','estado']
    readonly_fields = ['origen','version']
    def has_change_permission(self,request,obj=None):
        return super().has_change_permission(request,obj) and (obj is None or puede_editar(request.user,obj))
    def has_delete_permission(self,request,obj=None):
        return super().has_delete_permission(request,obj) and (obj is None or puede_editar(request.user,obj))
    def get_readonly_fields(self,request,obj=None):
        return self.readonly_fields + (['laboratorio'] if obj else [])
    def formfield_for_foreignkey(self,db_field,request,**kwargs):
        if db_field.name=='laboratorio' and not request.user.is_superuser:
            kwargs['queryset']=Laboratorio.objects.filter(responsable=request.user)
        return super().formfield_for_foreignkey(db_field,request,**kwargs)
@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ['id','equipo','solicitante','tecnico','estado']
    readonly_fields = ['origen','creada']
admin.site.register(Mantenimiento)
@admin.register(Laboratorio)
class LaboratorioAdmin(admin.ModelAdmin):
    list_display=['nombre','responsable']
    def get_readonly_fields(self,request,obj=None):
        if obj and Traslado.objects.filter(Q(origen=obj)|Q(destino=obj),estado='Pendiente').exists():
            return ['responsable']
        return []

@admin.register(Traslado)
class TrasladoAdmin(admin.ModelAdmin):
    list_display=['equipo','origen','destino','solicitante','estado','creado']
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ['fecha','usuario','accion','objeto']
    def has_add_permission(self,request): return False
    def has_change_permission(self,request,obj=None): return False
    def has_delete_permission(self,request,obj=None): return False
