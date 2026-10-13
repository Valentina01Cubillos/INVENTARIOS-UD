import json
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from lab.importing import importar

class Command(BaseCommand):
    help = 'Migrar conservando originales y pendientes. Simula salvo --apply.'
    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--user', required=True)
        parser.add_argument('--report', default='importacion.json')
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options['user']).first()
        if not user: raise CommandError('El usuario no existe.')
        try: report = importar(user, apply=options['apply'])
        except (ValueError, KeyError) as exc: raise CommandError(str(exc)) from exc
        Path(options['report']).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        self.stdout.write(f"Equipos nuevos: {report['equipos']}; solicitudes: {report['solicitudes']}; mantenimientos: {report['mantenimientos']}; pendientes: {len(report['incidencias'])}; filas conservadas: {report['registros_preservados']}")
