from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea el grupo Operario (edición rápida)"

    def handle(self, *args, **options):
        Group.objects.get_or_create(name="Operario")
        self.stdout.write("Grupo Operario OK")
