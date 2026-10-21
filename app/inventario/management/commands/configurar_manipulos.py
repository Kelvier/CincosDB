from django.core.management.base import BaseCommand
from inventario.models import Contador, PiezaManipulo, Uso

COMUN = ["HOCA-001", "HOCA-004", "HOCA-005", "HOCA-006", "HOCA-007", "HOCA-008",
         "HOCA-009", "HOCA-010", "HOCA-011", "HOCA-012", "HOCA-015", "HOCA-016"]
BLANCO = ["HOCA-002", "HOCA-003"]
GRIS = ["HOCA-013", "HOCA-014"]
FACIAL_QUITA = {"HOCA-009", "HOCA-016"}                 # sustituidas por las faciales
FACIAL_EXTRA = {"HOCA-017": 1, "HOCA-018": 1, "HOCA-019": 1}
FACIAL_CANT = {"HOCA-012": 2}                           # solo 2 sensores de temperatura

ETIQUETAS = {
    "manipulos_terminados": "Nacionales terminados",
    "manipulos_inter": "Internacionales terminados",
}


class Command(BaseCommand):
    help = "Asigna las piezas a cada tipo de manipulo. No pisa lo que ya exista."

    def handle(self, *args, **opts):
        P = {p.codigo: p for p in PiezaManipulo.objects.all()}
        plan = {"nacional": {c: P[c].por_unidad for c in COMUN + BLANCO if c in P},
                "internacional": {c: P[c].por_unidad for c in COMUN + GRIS if c in P}}
        fac = {c: P[c].por_unidad for c in COMUN + BLANCO if c in P and c not in FACIAL_QUITA}
        fac.update(FACIAL_EXTRA)
        fac.update(FACIAL_CANT)
        plan["facial"] = fac
        for var, piezas in plan.items():
            for codigo, cant in piezas.items():
                if codigo not in P:
                    self.stdout.write(self.style.WARNING(f"Falta {codigo}, se omite"))
                    continue
                Uso.objects.get_or_create(pieza=P[codigo], variante=var, defaults={"cantidad": cant})
        Contador.objects.get_or_create(clave="manipulos_facial", defaults=dict(
            grupo="manipulo", etiqueta="Faciales terminados", valor=0))
        for clave, et in ETIQUETAS.items():
            Contador.objects.filter(clave=clave).update(etiqueta=et)
        for var in plan:
            self.stdout.write(f"{var}: {Uso.objects.filter(variante=var).count()} piezas")
