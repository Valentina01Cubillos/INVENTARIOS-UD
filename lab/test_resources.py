"""Resource portability, exact copies and complete backups."""
from io import BytesIO,StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import hashlib
import json
import sqlite3
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import SimpleTestCase,TestCase
from openpyxl import load_workbook
from PIL import Image
from .legacy_excel import HojaVidaService
from .legacy_photo import FotoService
from .models import Equipo,Laboratorio

class RecursosPropiosTests(TestCase):
    def test_recursos_locales_y_copias_exactas(self):
        root=Path(settings.RESOURCES_ROOT).resolve()
        self.assertTrue(root.is_relative_to(Path(settings.BASE_DIR).resolve()))
        manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['file_count'],len(manifest['files']))
        for entry in manifest['files']:
            path=root/entry['path']
            self.assertTrue(path.resolve().is_relative_to(root))
            self.assertEqual(path.stat().st_size,entry['bytes'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),entry['sha256'])
        self.assertEqual(len(list((root/'inventarios').glob('*.xlsx'))),6)

    def test_foto_excel_pdf_solo_con_recursos_propios(self):
        from .documents import generar
        path=FotoService().obtener_foto('ACER','V226HQL')
        self.assertTrue(path.is_relative_to(settings.RESOURCES_ROOT))
        with Image.open(path) as image:image.verify()
        equipo=Equipo.objects.create(laboratorio=Laboratorio.objects.create(nombre='603'),descripcion='Monitor',placa='R001',marca='ACER',modelo='V226HQL')
        wb=load_workbook(generar(equipo,'xlsx'))
        self.assertEqual(wb.active['H13'].value,'R001')
        self.assertTrue(wb.active._images)
        wb.close()
        self.assertTrue(generar(equipo,'pdf').read().startswith(b'%PDF'))

    def test_importacion_copiada_idempotente(self):
        from .importing import importar
        from .models import Solicitud,Mantenimiento,RegistroLegacy
        user=User.objects.create_user('importador_recursos')
        result=importar(user,apply=True)
        self.assertEqual(len(result['fuentes']),8)
        self.assertGreater(result['equipos'],0)
        self.assertGreater(result['solicitudes'],0)
        self.assertGreater(result['mantenimientos'],0)
        counts=[model.objects.count() for model in (Equipo,Solicitud,Mantenimiento,RegistroLegacy)]
        second=importar(user,apply=True)
        self.assertEqual(second['equipos'],0)
        self.assertEqual(second['solicitudes'],0)
        self.assertEqual(second['mantenimientos'],0)
        self.assertEqual(counts,[model.objects.count() for model in (Equipo,Solicitud,Mantenimiento,RegistroLegacy)])

class RespaldoRecursosTests(SimpleTestCase):
    def test_respaldo_incluye_fuentes_plantillas_fotos_y_medios(self):
        from .management.commands.respaldar import Command
        with TemporaryDirectory() as directory:
            root=Path(directory)
            database=root/'active.sqlite3'
            with sqlite3.connect(database) as conn:
                conn.execute('CREATE TABLE ejemplo (valor TEXT)')
                conn.execute('INSERT INTO ejemplo VALUES (?)',('preservado',))
            conn.close()
            media=root/'media';media.mkdir();(media/'documento.txt').write_text('documento',encoding='utf-8')
            command=Command(stdout=StringIO())
            config=SimpleNamespace(DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':database}},MEDIA_ROOT=media,RESOURCES_ROOT=settings.RESOURCES_ROOT,BASE_DIR=settings.BASE_DIR)
            with patch('lab.management.commands.respaldar.settings',config):command.handle(destino=str(root/'backups'))
            backup=next((root/'backups').iterdir())
            self.assertEqual((backup/'private_media/documento.txt').read_text(encoding='utf-8'),'documento')
            self.assertTrue((backup/'resources/plantillas/HojaVida.xlsx').is_file())
            self.assertTrue((backup/'resources/base_datos/BASE_DATOS.xlsx').is_file())
            self.assertTrue((backup/'resources/mantenimientos/REPORTE_MANTENIMIENTOS.xlsx').is_file())
            self.assertTrue((backup/'resources/fotos/ACER_V226HQL.jpg').is_file())
            self.assertEqual(len(list((backup/'resources/inventarios').glob('*.xlsx'))),6)
            with sqlite3.connect(backup/'database.sqlite3') as conn:
                self.assertEqual(conn.execute('SELECT valor FROM ejemplo').fetchone()[0],'preservado')
            conn.close()
