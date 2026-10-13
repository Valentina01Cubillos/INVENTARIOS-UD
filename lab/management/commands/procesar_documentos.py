from django.core.management.base import BaseCommand
from lab.jobs import process
from lab.models import TrabajoDocumento
class Command(BaseCommand):
    help='Procesar un trabajo o todos los trabajos documentales pendientes.'
    def add_arguments(self,parser): parser.add_argument('--job',type=int)
    def handle(self,*args,**options):
        ids=[options['job']] if options['job'] else list(TrabajoDocumento.objects.filter(estado='Pendiente').values_list('pk',flat=True))
        for pk in ids: process(pk)
