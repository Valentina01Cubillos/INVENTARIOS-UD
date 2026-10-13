import re
from django.db import migrations, models


def numerar(apps, schema_editor):
    Solicitud=apps.get_model('lab','Solicitud')
    Secuencia=apps.get_model('lab','SecuenciaSolicitud')
    alias=schema_editor.connection.alias
    ultimo=0
    for codigo in Solicitud.objects.using(alias).values_list('codigo_legacy',flat=True):
        match=re.fullmatch(r'S-(\d+)',codigo or '',re.IGNORECASE)
        if match: ultimo=max(ultimo,int(match.group(1)))
    for solicitud in Solicitud.objects.using(alias).filter(codigo_legacy='').order_by('pk'):
        ultimo+=1
        solicitud.codigo_legacy=f'S-{ultimo}'
        solicitud.save(update_fields=['codigo_legacy'])
    Secuencia.objects.using(alias).update_or_create(pk=1,defaults={'ultimo':ultimo})


class Migration(migrations.Migration):
    dependencies=[('lab','0005_laboratorio_responsable_traslado')]
    operations=[
        migrations.CreateModel(name='SecuenciaSolicitud',fields=[('id',models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name='ID')),('ultimo',models.PositiveIntegerField(default=0))]),
        migrations.RunPython(numerar,migrations.RunPython.noop),
    ]
