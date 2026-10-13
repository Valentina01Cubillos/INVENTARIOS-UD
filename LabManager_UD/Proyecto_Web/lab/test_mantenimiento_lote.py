from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import User, Permission
from .models import Equipo, Laboratorio, Mantenimiento, Auditoria

class MantenimientoLoteTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('tecnico_lote')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='lab',codename='add_mantenimiento'))
        self.client.force_login(self.user)
        self.room=Laboratorio.objects.create(nombre='Salón 603')
        self.equipos=[Equipo.objects.create(descripcion=f'Equipo {i}',laboratorio=self.room) for i in range(4)]
        self.payload={'laboratorio':self.room.pk,'equipos':[e.pk for e in self.equipos],'fecha':'2026-10-02','hora_inicio':'08:00','hora_fin':'10:00','tipo':'MIPV','diagnostico':'Revisión del equipo','especificaciones':'Limpieza y comprobación','estado':'Operativo'}
    def test_reparto_y_reportes(self):
        self.assertEqual(self.client.post('/mantenimientos/lote/',self.payload).status_code,302)
        records=list(Mantenimiento.objects.all())
        self.assertEqual(len(records),4)
        self.assertEqual(len({r.lote for r in records}),1)
        self.assertTrue(all(r.minutos_asignados==Decimal(30) and r.tecnico==self.user for r in records))
        self.assertEqual(Auditoria.objects.count(),4)
    def test_equipo_ajeno_al_salon(self):
        other=Equipo.objects.create(descripcion='Ajeno',laboratorio=Laboratorio.objects.create(nombre='604'))
        self.payload['equipos'].append(other.pk)
        self.assertEqual(self.client.post('/mantenimientos/lote/',self.payload).status_code,200)
        self.assertFalse(Mantenimiento.objects.exists())
    def test_franja_invalida_y_sin_equipos(self):
        for change in [{'hora_fin':'08:00'},{'hora_fin':'07:00'},{'equipos':[]}]:
            self.client.post('/mantenimientos/lote/',{**self.payload,**change})
            self.assertFalse(Mantenimiento.objects.exists())
    def test_fraccion_no_redondeada_al_guardar(self):
        self.client.post('/mantenimientos/lote/',{**self.payload,'hora_fin':'08:01','equipos':[e.pk for e in self.equipos[:3]]})
        records=list(Mantenimiento.objects.all())
        self.assertEqual(len(records),3)
        self.assertTrue(all(r.segundos_totales==60 and r.cantidad_equipos==3 for r in records))
    def test_transaccion_completa(self):
        with patch('lab.views.audit',side_effect=RuntimeError('Fallo')):
            with self.assertRaises(RuntimeError): self.client.post('/mantenimientos/lote/',self.payload)
        self.assertFalse(Mantenimiento.objects.exists())
    def test_permisos_y_checklist(self):
        response=self.client.get('/mantenimientos/lote/',{'laboratorio':self.room.pk})
        self.assertContains(response,'Equipo 0')
        self.user.user_permissions.clear()
        self.assertEqual(self.client.post('/mantenimientos/lote/',self.payload).status_code,403)
