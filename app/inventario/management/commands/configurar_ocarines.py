from django.core.management.base import BaseCommand
from inventario.models import Contador, PiezaOcarina, UsoOcarina

# Plasticos exteriores: blanco (nacional) y su sustituto gris (internacional)
BLANCO = ["DOCA-003", "DOCA-006", "DOCA-007", "DOCA-010"]
GRIS = ["DOCA-034", "DOCA-033", "DOCA-036", "DOCA-035"]
NINGUNO = {"DOCA-037"}      # soporte manipulo facial: no lo usa ninguna ocarine

ETIQUETAS = {
    "ocarines_acabadas": "Ocarines nacionales acabadas",
    "oc_int_fin": "Ocarines internacionales acabadas",
}


class Command(BaseCommand):
    help = "Asigna las piezas a cada tipo de ocarine. No pisa lo que ya exista."

    def handle(self, *args, **opts):
        P = {p.codigo: p for p in PiezaOcarina.objects.all()}
        excluidas = set(BLANCO) | set(GRIS) | NINGUNO
        comun = [c for c in P if c not in excluidas]
        plan = {"nacional": comun + BLANCO, "internacional": comun + GRIS}
        for var, codigos in plan.items():
            for codigo in codigos:
                if codigo not in P:
                    self.stdout.write(self.style.WARNING(f"Falta {codigo}, se omite"))
                    continue
                UsoOcarina.objects.get_or_create(pieza=P[codigo], variante=var,
                                                 defaults={"cantidad": P[codigo].por_unidad})
        for clave, et in ETIQUETAS.items():
            Contador.objects.filter(clave=clave).update(etiqueta=et)
        for var in plan:
            self.stdout.write(f"{var}: {UsoOcarina.objects.filter(variante=var).count()} piezas")
