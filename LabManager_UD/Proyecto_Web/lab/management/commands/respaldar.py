from datetime import datetime
from contextlib import closing
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help='Respaldar base, archivos privados y recursos propios; nunca muestra credenciales.'
    def add_arguments(self,parser): parser.add_argument('--destino',default='backups')
    def handle(self,*args,**options):
        dest=Path(options['destino'])/datetime.now().strftime('%Y%m%d_%H%M%S')
        dest.mkdir(parents=True,exist_ok=False)
        db=settings.DATABASES['default']
        if db['ENGINE'].endswith('sqlite3'):
            with closing(sqlite3.connect(db['NAME'])) as source, closing(sqlite3.connect(dest/'database.sqlite3')) as target: source.backup(target)
        else:
            env=os.environ.copy(); env['PGPASSWORD']=db.get('PASSWORD','')
            portable=settings.BASE_DIR/'.runtime/pgsql/bin/pg_dump.exe'
            executable=str(portable) if portable.exists() else 'pg_dump'
            try:
                subprocess.run([executable,'-h',db['HOST'],'-p',str(db['PORT']),'-U',db['USER'],'-Fc','-f',str(dest/'database.dump'),db['NAME']],env=env,check=True,capture_output=True)
            except (OSError,subprocess.CalledProcessError) as exc: raise CommandError('No se pudo respaldar PostgreSQL. Verifique pg_dump y el acceso a la base.') from exc
        if Path(settings.MEDIA_ROOT).exists(): shutil.copytree(settings.MEDIA_ROOT,dest/'private_media')
        if Path(settings.RESOURCES_ROOT).exists(): shutil.copytree(settings.RESOURCES_ROOT,dest/'resources')
        self.stdout.write('Respaldo creado: '+str(dest))
