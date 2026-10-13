from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.utils import timezone
from .models import Equipo, Laboratorio, Solicitud, Mantenimiento, AparienciaPerfil

HOJA_CAMPOS = [
    'FECHA DE ADQUISICIÓN', '# DE FACTURA COMPRA', 'FRECUENCIA DE MTTO', 'PROVEEDOR',
    '# DE REMISIÓN COMPRA', 'VALOR DE COMPRA', 'PAÍS DE ORIGEN', 'REFERENCIA/MODELO',
    'TIEMPO DE GARANTÍA', 'TIEMPO DE VIDA ÚTIL', 'POTENCIA ELÉCTRICA', 'TIPO DE USO',
    '2. ESPECIFICACIONES TÉCNICAS', '¿Cuenta con manual?', 'Accesorios',
]

class EquipoForm(forms.ModelForm):
    version = forms.IntegerField(widget=forms.HiddenInput, initial=1)
    class Meta:
        model = Equipo
        exclude = ['origen','datos_hoja_vida','datos_origen','foto']
        labels = {'numero_interno':'Número interno','descripcion':'Descripción','inventario_fisico':'Inventario físico'}

class FotoForm(forms.Form):
    foto = forms.ImageField(label='Fotografía (máximo 8 MB)')
    def clean_foto(self):
        photo = self.cleaned_data['foto']
        if photo.size > 8 * 1024 * 1024: raise forms.ValidationError('La imagen supera 8 MB.')
        if photo.image.width * photo.image.height > 25_000_000: raise forms.ValidationError('La imagen supera 25 megapíxeles.')
        return photo

class HojaVidaForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput)
    def __init__(self, *args, equipo, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['version'] = equipo.version
        self.mapping = {}
        for i, name in enumerate(HOJA_CAMPOS):
            field = f'dato_{i}'
            self.mapping[field] = name
            self.fields[field] = forms.CharField(label=name, required=False, initial=equipo.datos_hoja_vida.get(name,''), widget=forms.Textarea(attrs={'rows':2}) if i in (12,14) else forms.TextInput())
    def datos(self, original):
        return {**original, **{name:self.cleaned_data[field] for field,name in self.mapping.items()}}

class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ['equipo','tipo','nombre_solicitante','documento','celular','tipo_solicitante','fecha_reporte','hora_reporte','asignatura','banco','descripcion','observaciones']
        labels = {'nombre_solicitante':'Nombre del solicitante','documento':'Documento de identidad','tipo_solicitante':'Tipo de solicitante','descripcion':'Descripción de la falla o actividad'}
        widgets = {'fecha_reporte':forms.DateInput(attrs={'type':'date'}),'hora_reporte':forms.TimeInput(attrs={'type':'time'})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['equipo'].required = True
        self.fields['nombre_solicitante'].required = True
        self.fields['tipo_solicitante'].widget = forms.Select(choices=[('Estudiante','Estudiante'),('Docente','Docente'),('Técnico','Técnico'),('Monitor','Monitor'),('Contratista','Contratista'),('Otro','Otro')])
        self.initial.setdefault('fecha_reporte',timezone.localdate())
        self.initial.setdefault('hora_reporte',timezone.localtime().time().replace(microsecond=0))

class SolicitarMantenimientoForm(forms.ModelForm):
    class Meta:
        model=Solicitud
        fields=['equipo','nombre_solicitante','tipo','descripcion','observaciones']
        labels={'nombre_solicitante':'Nombre del solicitante','descripcion':'Razón de mantenimiento','observaciones':'Observaciones (opcionales)'}
        widgets={'descripcion':forms.Textarea(attrs={'rows':4}),'observaciones':forms.Textarea(attrs={'rows':3})}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['equipo'].required=True
        self.fields['nombre_solicitante'].required=True
        self.fields['nombre_solicitante'].help_text='Persona que solicita el mantenimiento, aunque no tenga cuenta en el sistema.'

class AsignarForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput)
    tecnico = forms.ModelChoiceField(queryset=get_user_model().objects.none(),label='Técnico responsable')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from django.db.models import Q
        self.fields['tecnico'].queryset=get_user_model().objects.filter(is_active=True).filter(Q(is_superuser=True)|Q(groups__permissions__content_type__app_label='lab',groups__permissions__codename='add_mantenimiento')|Q(user_permissions__content_type__app_label='lab',user_permissions__codename='add_mantenimiento')).distinct()

class CancelarForm(forms.Form):
    version = forms.IntegerField(widget=forms.HiddenInput)
    motivo = forms.CharField(label='Motivo de cancelación',widget=forms.Textarea(attrs={'rows':3}))

class MantenimientoForm(forms.ModelForm):
    class Meta:
        model = Mantenimiento
        exclude = ['tecnico','origen','responsable_legacy','datos_legacy','version']
        widgets = {'fecha':forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}),'estado':forms.Select(choices=[('Operativo','Operativo'),('En reparación','En reparación'),('No operativo','No operativo'),('Pendiente de repuesto','Pendiente de repuesto')])}
        labels = {'diagnostico':'Diagnóstico','especificaciones':'Mantenimiento realizado','enlace_repuesto':'Enlace del repuesto','garantia':'Garantía'}
    def __init__(self,*args,**kwargs):
        solicitud_contexto=kwargs.pop('solicitud_contexto',None)
        super().__init__(*args,**kwargs)
        self.fields['equipo'].required=True
        self.fields['fecha'].required=True
        self.fields['diagnostico'].required=True
        self.fields['observaciones'].required=False
        self.initial.setdefault('fecha',timezone.localdate())
        if solicitud_contexto:
            self.initial.update(solicitud=solicitud_contexto.pk,tipo=solicitud_contexto.tipo,equipo=solicitud_contexto.equipo_id)
            for name in ('solicitud','tipo'):
                self.fields[name].disabled=True
                self.fields[name].widget=forms.HiddenInput()
            if solicitud_contexto.equipo_id:
                self.fields['equipo'].disabled=True
                self.fields['equipo'].widget=forms.HiddenInput()
            else:
                self.fields['equipo'].required=False
                self.fields['equipo'].disabled=True
                self.fields['equipo'].widget=forms.HiddenInput()
    def clean(self):
        data=super().clean(); solicitud=data.get('solicitud')
        if solicitud and solicitud.equipo_id and solicitud.equipo_id != getattr(data.get('equipo'),'pk',None):
            raise forms.ValidationError('La solicitud pertenece a otro equipo. Primero vincula el registro histórico si es necesario.')
        return data

class LaboratorioForm(forms.ModelForm):
    class Meta:
        model=Laboratorio
        fields=['nombre','responsable']

class TrasladoForm(forms.Form):
    destino = forms.ModelChoiceField(queryset=Laboratorio.objects.none(), label='Laboratorio de destino')
    justificacion = forms.CharField(label='Justificación del traslado', max_length=3000, widget=forms.Textarea(attrs={'rows':4}))
    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['destino'].queryset = Laboratorio.objects.filter(responsable=user).order_by('nombre')

class MantenimientoLoteForm(forms.Form):
    laboratorio = forms.ModelChoiceField(queryset=Laboratorio.objects.order_by('nombre'), label='Salón / laboratorio')
    equipos = forms.ModelMultipleChoiceField(queryset=Equipo.objects.none(), widget=forms.CheckboxSelectMultiple, label='Equipos en mantenimiento')
    fecha = forms.DateField(initial=timezone.localdate, widget=forms.DateInput(attrs={'type':'date'}))
    hora_inicio = forms.TimeField(widget=forms.TimeInput(attrs={'type':'time'}))
    hora_fin = forms.TimeField(widget=forms.TimeInput(attrs={'type':'time'}))
    tipo = forms.ChoiceField(choices=Solicitud._meta.get_field('tipo').choices, initial='MIPV')
    especificaciones = forms.CharField(label='Mantenimiento realizado (común para los equipos)', widget=forms.Textarea(attrs={'rows':3}))
    diagnostico = forms.CharField(label='Diagnóstico', widget=forms.Textarea(attrs={'rows':2}))
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows':2}))
    estado = forms.ChoiceField(choices=[('Operativo','Operativo'),('En reparación','En reparación'),('No operativo','No operativo'),('Pendiente de repuesto','Pendiente de repuesto')])
    def __init__(self, *args, laboratorio_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        if str(laboratorio_id or '').isdigit():
            self.fields['equipos'].queryset = Equipo.objects.filter(laboratorio_id=laboratorio_id).order_by('descripcion','placa','pk')
    def clean(self):
        from datetime import datetime, date
        data = super().clean()
        inicio, fin = data.get('hora_inicio'), data.get('hora_fin')
        if inicio and fin:
            seconds = int((datetime.combine(date.today(),fin)-datetime.combine(date.today(),inicio)).total_seconds())
            if seconds <= 0: self.add_error('hora_fin','La hora de fin debe ser posterior a la de inicio en la misma fecha.')
            else: data['segundos_totales'] = seconds
        return data

class ConciliarForm(forms.Form):
    equipo=forms.ModelChoiceField(queryset=Equipo.objects.select_related('laboratorio').order_by('laboratorio__nombre','descripcion'))
    nota=forms.CharField(widget=forms.Textarea(attrs={'rows':2}),required=True,label='Justificación de la vinculación')

class ImportarForm(forms.Form):
    archivo=forms.FileField(required=False,label='Inventario Excel opcional (nombre con código del laboratorio)')
    accion=forms.ChoiceField(choices=[('simular','Simular'),('aplicar','Importar y conservar los registros')])
    def clean_archivo(self):
        value=self.cleaned_data.get('archivo')
        if value and (not value.name.lower().endswith('.xlsx') or value.size > 20*1024*1024):
            raise forms.ValidationError('Use un archivo .xlsx de hasta 20 MB.')
        return value

class UsuarioForm(UserCreationForm):
    grupos=forms.ModelMultipleChoiceField(queryset=Group.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    class Meta(UserCreationForm.Meta):
        model=get_user_model()
        fields=['username','first_name','last_name','email']

class PerfilForm(forms.ModelForm):
    class Meta:
        model=get_user_model()
        fields=['username','first_name','last_name','email']

class FotoPerfilWidget(forms.ClearableFileInput):
    def render(self,name,value,attrs=None,renderer=None):
        from django.template.loader import render_to_string
        return render_to_string('perfil_foto_input.html',self.get_context(name,value,attrs))

class AparienciaForm(forms.ModelForm):
    class Meta:
        model=AparienciaPerfil
        fields=['primario','secundario','fondo','avatar','portada']
        labels={'primario':'Color principal','secundario':'Color de acento','fondo':'Fondo de la pantalla','avatar':'Foto de perfil','portada':'Foto de portada'}
        widgets={key:forms.TextInput(attrs={'type':'color'}) for key in ('primario','secundario','fondo')}
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for key in ('avatar','portada'):
            self.fields[key].widget=FotoPerfilWidget(attrs={'accept':'image/jpeg,image/png,image/webp'})
    def clean(self):
        data=super().clean()
        for key in ('avatar','portada'):
            photo=data.get(key)
            if photo and hasattr(photo,'content_type'):
                if photo.size>4*1024*1024: self.add_error(key,'Usa una imagen de hasta 4 MB.')
                elif photo.image.width*photo.image.height>20_000_000: self.add_error(key,'Usa una imagen de hasta 20 megapíxeles.')
        return data

class EditarUsuarioForm(forms.ModelForm):
    grupos=forms.ModelMultipleChoiceField(queryset=Group.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    class Meta:
        model=get_user_model()
        fields=['username','first_name','last_name','email','is_active']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk: self.initial['grupos']=self.instance.groups.all()
