from django.conf import settings
from django.core.validators import RegexValidator
from django.db import migrations,models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies=[('lab','0006_secuencia_solicitud'),migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations=[migrations.CreateModel(name='AparienciaPerfil',fields=[
        ('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),
        ('primario',models.CharField(default='#b33e49',max_length=7,validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])),
        ('secundario',models.CharField(default='#f2cb62',max_length=7,validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])),
        ('fondo',models.CharField(default='#f8f6f3',max_length=7,validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])),
        ('avatar',models.ImageField(blank=True,upload_to='perfiles/')),
        ('portada',models.ImageField(blank=True,upload_to='perfiles/')),
        ('usuario',models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,related_name='apariencia',to=settings.AUTH_USER_MODEL)),
    ])]
