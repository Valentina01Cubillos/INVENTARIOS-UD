import logging
import os
import subprocess
import sys
import zipfile
from tempfile import TemporaryDirectory
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.utils import timezone
from .models import Equipo, TrabajoDocumento
from .documents import generar

logger=logging.getLogger(__name__)

def launch(pk):
    kwargs={'cwd':str(settings.BASE_DIR),'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
    if os.name=='nt': kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
    else: kwargs['start_new_session']=True
    try:
        subprocess.Popen([sys.executable,str(settings.BASE_DIR/'manage.py'),'procesar_documentos','--job',str(pk)],**kwargs)
    except OSError:
        TrabajoDocumento.objects.filter(pk=pk).update(estado='Error',errores=['No se pudo iniciar el procesador. Ejecute manage.py procesar_documentos --job '+str(pk)])

def process(pk):
    # Compare-and-set claim works across separate worker processes.
    claimed=TrabajoDocumento.objects.filter(pk=pk,estado='Pendiente').update(estado='Procesando',actualizado=timezone.now())
    if not claimed: return
    job=TrabajoDocumento.objects.select_related('usuario').get(pk=pk)
    errors=[]; count=0
    try:
        if not job.usuario.is_active or not job.usuario.has_perm('lab.view_equipo'):
            raise RuntimeError('El usuario ya no tiene acceso al inventario.')
        with TemporaryDirectory(prefix='lab-batch-') as directory:
            target=Path(directory)/'hojas.zip'
            with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                for i,pk_equipo in enumerate(job.equipos,1):
                    try:
                        eq=Equipo.objects.select_related('laboratorio').get(pk=pk_equipo)
                        archive.writestr(f'HV_{eq.pk}.{job.formato}',generar(eq,job.formato).getvalue()); count+=1
                    except Exception:
                        logger.exception('Error en equipo %s, trabajo %s',pk_equipo,job.pk)
                        errors.append(f'No se pudo generar el equipo {pk_equipo}.')
                    TrabajoDocumento.objects.filter(pk=job.pk).update(progreso=i,actualizado=timezone.now())
                if errors: archive.writestr('incidencias.txt','\n'.join(errors))
            if count:
                with target.open('rb') as stream: job.archivo.save(f'hojas_{job.pk}.zip',File(stream),save=False)
            job.estado='Parcial' if count and errors else 'Completado' if count else 'Error'
            job.errores=errors; job.save(update_fields=['archivo','estado','errores','actualizado'])
    except Exception as exc:
        logger.exception('Error de exportación %s',job.pk)
        job.estado='Error'; job.errores=[str(exc)]; job.save(update_fields=['estado','errores','actualizado'])
