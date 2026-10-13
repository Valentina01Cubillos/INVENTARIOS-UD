from django.conf import settings
from django.db import models
from django.db import transaction
from django.core.validators import RegexValidator

class AparienciaPerfil(models.Model):
    usuario=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='apariencia')
    primario=models.CharField(max_length=7,default='#d82935',validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])
    secundario=models.CharField(max_length=7,default='#f2cb62',validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])
    fondo=models.CharField(max_length=7,default='#f8f6f3',validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])
    avatar=models.ImageField(upload_to='perfiles/',blank=True)
    portada=models.ImageField(upload_to='perfiles/',blank=True)

TIPOS_MANTENIMIENTO = [
    ('MIC', 'Interno correctivo (MIC)'), ('MEC', 'Externo correctivo (MEC)'),
    ('MIP', 'Interno predictivo (MIP)'), ('MEP', 'Externo predictivo (MEP)'),
    ('MIPV', 'Interno preventivo (MIPV)'), ('MEPV', 'Externo preventivo (MEPV)'),
    ('Correctivo', 'Correctivo'), ('Preventivo', 'Preventivo'),
]
class Laboratorio(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='laboratorios_responsables')
    def __str__(self): return self.nombre
class Equipo(models.Model):
    placa = models.CharField(max_length=100,blank=True,db_index=True)
    numero_interno = models.CharField(max_length=100,blank=True,db_index=True)
    serial = models.CharField(max_length=200,blank=True)
    descripcion = models.TextField()
    laboratorio = models.ForeignKey(Laboratorio,on_delete=models.PROTECT)
    marca = models.CharField(max_length=200,blank=True)
    modelo = models.CharField(max_length=200,blank=True)
    estado = models.CharField(max_length=100,blank=True)
    funcionario = models.CharField(max_length=300,blank=True)
    inventario_fisico = models.CharField(max_length=100,blank=True)
    arka = models.CharField(max_length=100,blank=True)
    erp = models.CharField(max_length=100,blank=True)
    observaciones = models.TextField(blank=True)
    datos_hoja_vida = models.JSONField(default=dict,blank=True)
    origen = models.CharField(max_length=500,blank=True,unique=True,null=True)
    version = models.PositiveIntegerField(default=1)
    foto = models.ImageField(upload_to='fotos/%Y/%m/', blank=True)
    datos_origen = models.JSONField(default=dict, blank=True)
    def __str__(self): return f'{self.placa or self.numero_interno or self.pk} - {self.descripcion[:70]}'
class SecuenciaSolicitud(models.Model):
    ultimo = models.PositiveIntegerField(default=0)

class Solicitud(models.Model):
    ESTADOS = [('Pendiente','Pendiente'),('Asignada','Asignada'),('Cerrada','Finalizada'),('Cancelada','Cancelada')]
    equipo = models.ForeignKey(Equipo,on_delete=models.PROTECT,null=True,blank=True)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,null=True,blank=True,related_name='asignaciones')
    creada = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=30,choices=TIPOS_MANTENIMIENTO)
    descripcion = models.TextField()
    asignatura = models.CharField(max_length=200,blank=True)
    banco = models.CharField(max_length=100,blank=True)
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=30,choices=ESTADOS,default='Pendiente')
    codigo_legacy = models.CharField(max_length=100,blank=True)
    datos_legacy = models.JSONField(default=dict,blank=True)
    origen = models.CharField(max_length=500,unique=True,null=True,blank=True)
    nombre_solicitante = models.CharField(max_length=200, blank=True)
    documento = models.CharField(max_length=100, blank=True)
    celular = models.CharField(max_length=100, blank=True)
    tipo_solicitante = models.CharField(max_length=100, blank=True)
    fecha_reporte = models.DateField(null=True, blank=True)
    hora_reporte = models.TimeField(null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    @property
    def solicitante_nombre(self):
        nombre=self.nombre_solicitante.strip()
        if not nombre or nombre.casefold()==self.solicitante.username.casefold():
            return 'Solicitante por confirmar'
        return nombre
    @property
    def codigo(self): return self.codigo_legacy or (f'S-{self.pk}' if self.pk else 'Se asignará al guardar')
    def save(self,*args,**kwargs):
        if self._state.adding and not self.codigo_legacy:
            with transaction.atomic():
                secuencia,_=SecuenciaSolicitud.objects.get_or_create(pk=1)
                secuencia=SecuenciaSolicitud.objects.select_for_update().get(pk=secuencia.pk)
                import re
                for codigo in Solicitud.objects.values_list('codigo_legacy',flat=True):
                    match=re.fullmatch(r'S-(\d+)',codigo or '',re.IGNORECASE)
                    if match: secuencia.ultimo=max(secuencia.ultimo,int(match.group(1)))
                secuencia.ultimo+=1
                secuencia.save(update_fields=['ultimo'])
                self.codigo_legacy=f'S-{secuencia.ultimo}'
                return super().save(*args,**kwargs)
        return super().save(*args,**kwargs)
    @property
    def equipo_nombre(self):
        return str(self.equipo) if self.equipo_id else self.datos_legacy.get('equipo', 'Equipo histórico sin vincular')
    def __str__(self): return self.codigo
class Mantenimiento(models.Model):
    lote = models.UUIDField(null=True, blank=True, db_index=True, editable=False)
    hora_inicio = models.TimeField(null=True, blank=True, editable=False)
    hora_fin = models.TimeField(null=True, blank=True, editable=False)
    segundos_totales = models.PositiveIntegerField(null=True, blank=True, editable=False)
    cantidad_equipos = models.PositiveIntegerField(default=1, editable=False)
    @property
    def minutos_asignados(self):
        from decimal import Decimal
        if self.segundos_totales is None: return None
        return Decimal(self.segundos_totales) / Decimal(self.cantidad_equipos) / Decimal(60)
    @property
    def resumen_tiempo(self):
        if self.segundos_totales is None: return ''
        return f'Franja {self.hora_inicio:%H:%M}–{self.hora_fin:%H:%M}; {self.segundos_totales / 60:g} min / {self.cantidad_equipos} equipos = {self.minutos_asignados:.2f} min por equipo.'
    equipo = models.ForeignKey(Equipo,on_delete=models.PROTECT,null=True,blank=True)
    solicitud = models.ForeignKey(Solicitud,on_delete=models.PROTECT,null=True,blank=True)
    tecnico = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    fecha = models.DateField(null=True, blank=True)
    tipo = models.CharField(max_length=30,choices=TIPOS_MANTENIMIENTO)
    empresa = models.CharField(max_length=200,blank=True)
    garantia = models.CharField(max_length=200,blank=True)
    diagnostico = models.TextField(blank=True)
    especificaciones = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)
    repuestos = models.TextField(blank=True)
    enlace_repuesto = models.URLField(blank=True)
    estado = models.CharField(max_length=100,blank=True)
    datos_legacy = models.JSONField(default=dict,blank=True)
    responsable_legacy = models.CharField(max_length=200,blank=True)
    origen = models.CharField(max_length=500,unique=True,null=True,blank=True)
    version = models.PositiveIntegerField(default=1)
    @property
    def equipo_nombre(self):
        return str(self.equipo) if self.equipo_id else self.datos_legacy.get('equipo', 'Equipo histórico sin vincular')
class Traslado(models.Model):
    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, related_name='traslados')
    origen = models.ForeignKey(Laboratorio, on_delete=models.PROTECT, related_name='traslados_salida')
    destino = models.ForeignKey(Laboratorio, on_delete=models.PROTECT, related_name='traslados_entrada')
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='traslados_solicitados')
    aprobador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='traslados_recibidos')
    justificacion = models.TextField()
    estado_anterior = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=20, choices=[('Pendiente','Pendiente'),('Aprobado','Aprobado'),('Rechazado','Rechazado')], default='Pendiente')
    creado = models.DateTimeField(auto_now_add=True)
    resuelto = models.DateTimeField(null=True, blank=True)
    respuesta = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['equipo'], condition=models.Q(estado='Pendiente'), name='un_traslado_pendiente_por_equipo')]

class Auditoria(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=100)
    objeto = models.CharField(max_length=100)
    detalle = models.JSONField(default=dict)

class RegistroLegacy(models.Model):
    """Every nonempty source row, including unresolved rows, remains inspectable."""
    origen = models.CharField(max_length=500, unique=True)
    archivo = models.CharField(max_length=300)
    hoja = models.CharField(max_length=100)
    fila = models.PositiveIntegerField()
    categoria = models.CharField(max_length=30)
    datos = models.JSONField(default=dict)
    hash_archivo = models.CharField(max_length=64)
    estado = models.CharField(max_length=30, default='Pendiente')
    motivo = models.TextField(blank=True)
    equipo = models.ForeignKey(Equipo, on_delete=models.PROTECT, null=True, blank=True)
    actualizado = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['archivo', 'fila']
        permissions = [('importar_datos', 'Importar y conciliar datos históricos')]

class TrabajoDocumento(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    estado = models.CharField(max_length=30, default='Pendiente')
    formato = models.CharField(max_length=10)
    equipos = models.JSONField(default=list)
    progreso = models.PositiveIntegerField(default=0)
    archivo = models.FileField(upload_to='documentos/%Y/%m/', blank=True)
    errores = models.JSONField(default=list)
