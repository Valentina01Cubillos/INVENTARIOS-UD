from django.db import migrations,models
from django.core.validators import RegexValidator

def actualizar_rojo(apps,schema_editor):
    apps.get_model('lab','AparienciaPerfil').objects.using(schema_editor.connection.alias).filter(primario='#b33e49').update(primario='#d82935')

class Migration(migrations.Migration):
    dependencies=[('lab','0007_aparienciaperfil')]
    operations=[migrations.AlterField(model_name='aparienciaperfil',name='primario',field=models.CharField(default='#d82935',max_length=7,validators=[RegexValidator(r'^#[0-9a-fA-F]{6}$')])),migrations.RunPython(actualizar_rojo,migrations.RunPython.noop)]
