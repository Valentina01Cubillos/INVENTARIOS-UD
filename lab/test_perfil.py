from io import BytesIO
from tempfile import TemporaryDirectory
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,override_settings
from PIL import Image
from .models import AparienciaPerfil
from .appearance import foreground
from django.contrib.auth.models import Permission

class PerfilPersonalizadoTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('persona',first_name='Ana')
        self.other=User.objects.create_user('otra')
        self.client.force_login(self.user)
        self.payload={'username':'persona','first_name':'Ana','last_name':'Pérez','email':'', 'primario':'#345678','secundario':'#f1cc55','fondo':'#f9f7f4'}
        self.directory=TemporaryDirectory()
        self.media=override_settings(MEDIA_ROOT=self.directory.name)
        self.media.enable()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.media.disable)
    def image(self):
        data=BytesIO();Image.new('RGB',(600,500),'red').save(data,format='PNG')
        return SimpleUploadedFile('foto.png',data.getvalue(),content_type='image/png')
    def test_colores_por_cuenta_y_restaurar(self):
        self.assertContains(self.client.get('/perfil/'),'#d82935')
        self.assertEqual(self.client.post('/perfil/',self.payload).status_code,302)
        self.assertContains(self.client.get('/'),'--personal-primary:#345678')
        self.client.force_login(self.other)
        self.assertContains(self.client.get('/'),'--personal-primary:#d82935')
        self.assertFalse(AparienciaPerfil.objects.filter(usuario=self.other).exists())
        self.client.force_login(self.user)
        self.client.post('/perfil/',{**self.payload,'restaurar':'si'})
        self.assertEqual(AparienciaPerfil.objects.get(usuario=self.user).primario,'#d82935')
    def test_validacion_colores_y_contraste(self):
        response=self.client.post('/perfil/',{**self.payload,'primario':'red; color: blue'})
        self.assertEqual(response.status_code,200)
        self.assertIn('primario',response.context['preferencias'].errors)
        self.assertFalse(AparienciaPerfil.objects.exists())
        self.assertEqual(foreground('#ffffff'),'#17252c')
        self.assertEqual(foreground('#000000'),'#ffffff')
    def test_inicio_y_menu_por_permisos(self):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='lab',codename__in=['view_equipo','view_laboratorio','view_mantenimiento','add_mantenimiento']))
        response=self.client.get('/')
        self.assertNotContains(response,'class="admin-navigation"')
        self.assertContains(response,'Universidad Distrital')
        self.assertContains(response,'Francisco José de Caldas')
        self.assertContains(response,'class="dashboard-card"',count=4)
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='lab',codename='change_laboratorio'))
        self.assertContains(self.client.get('/'),'class="admin-navigation"')
    def test_fotos_personales_y_borrado(self):
        response=self.client.post('/perfil/',{**self.payload,'avatar':self.image(),'portada':self.image()})
        self.assertEqual(response.status_code,302)
        profile=AparienciaPerfil.objects.get(usuario=self.user)
        self.assertTrue(profile.avatar)
        self.assertTrue(profile.portada)
        response=self.client.get('/perfil/foto/avatar/')
        self.assertEqual(response.status_code,200)
        data=b''.join(response.streaming_content)
        photo=Image.open(BytesIO(data))
        self.assertEqual(photo.format,'JPEG')
        self.assertLessEqual(max(photo.size),400)
        self.assertContains(self.client.get('/perfil/'),'Quitar fotografía')
        self.assertContains(self.client.get('/'),'class="profile-cover"')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get('/perfil/foto/avatar/').status_code,404)
        self.client.force_login(self.user)
        self.client.post('/perfil/',{**self.payload,'avatar-clear':'on','portada-clear':'on'})
        profile.refresh_from_db();self.assertFalse(profile.avatar);self.assertFalse(profile.portada)
