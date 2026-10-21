from django.core.management.base import BaseCommand
from inventario.models import Contador, PiezaManipulo, PiezaOcarina

A, C, S = "ANIMA", "CERC", "CINCOS"

# codigo, nombre, inicial, x_maquina, restante, ideal, quien
OCARINAS = [
    ("DOCA-001", "Marco", 41, 1, 19, 10, A), ("DOCA-002", "Soporte manipulo", 38, 1, 16, 10, A),
    ("DOCA-003", "Parte arriba", 65, 1, 43, 10, A), ("DOCA-004", "Caja metalica", 49, 1, 27, 10, A),
    ("DOCA-005", "Chasis", 49, 1, 27, 10, A), ("DOCA-006", "Botonera", 65, 1, 43, 10, A),
    ("DOCA-007", "Cubierta pantalla", 66, 1, 44, 10, A), ("DOCA-008", "Lateral LED (gris)", 161, 1, 117, 20, A),
    ("DOCA-009", "Reflector led lateral", 175, 2, 131, 20, A), ("DOCA-010", "Parte abajo", 54, 1, 32, 10, A),
    ("DOCA-011", "Patas", 172, 4, 84, 40, A), ("DOCA-012", "Tornillos", 30000, 31, 29318, 310, A),
    ("DOCA-013", "Pantalla", 62, 1, 40, 10, C), ("DOCA-014", "Cable pantalla", 49, 1, 27, 10, C),
    ("DOCA-015", "Ferrita pantalla", 57, 1, 35, 10, C), ("DOCA-016", "Cable ocarine", 117, 1, 95, 10, C),
    ("DOCA-017", "Conector corriente", 50, 1, 28, 10, C), ("DOCA-018", "Fusible", 57, 2, 13, 20, C),
    ("DOCA-019", "Fuentes alimentacion", 48, 1, 26, 10, C), ("DOCA-020", "Cable al interior", 49, 1, 27, 10, C),
    ("DOCA-021", "Cable sold-manipulo", 62, 1, 40, 10, C), ("DOCA-022", "Cable-tierra", 31, 2, -13, 20, C),
    ("DOCA-023", "Cable al-boton", 45, 1, 23, 10, C), ("DOCA-024", "Cable boton-placa", 49, 1, 27, 10, C),
    ("DOCA-025", "Ferrita alimentacion", 72, 1, 50, 10, C), ("DOCA-026", "Placa ocarine", 30, 1, 8, 10, C),
    ("DOCA-027", "Placa LED", 222, 4, 134, 40, C), ("DOCA-028", "Ferrita LED", 216, 2, 172, 20, C),
    ("DOCA-030", "Cable LED", 118, 4, 30, 40, C), ("DOCA-031", "Bridas Envios", 73, 2, 29, 20, S),
    ("DOCA-032", "Botones", 25, 1, 3, 10, S), ("DOCA-033", "Botonera gris", 13, 1, 2, 10, A),
    ("DOCA-034", "Parte de arriba gris", 10, 1, 5, 10, A), ("DOCA-035", "Parte de abajo gris", 13, 1, 5, 10, A),
    ("DOCA-036", "Parte pantalla gris", 13, 1, 5, 10, A), ("DOCA-037", "Soporte manipulo facial", 22, 0, 22, 0, A),
]

# codigo, nombre, inicial, x_manipulo, restante, ideal, reutilizable, reciclados, quien
MANIPULOS = [
    ("HOCA-001", "Medialuna", 690, 2, 644, 20, 1, 46, A), ("HOCA-002", "Anillo manipulo blanco", 131, 1, 108, 10, 0, 0, A),
    ("HOCA-003", "Cuerpo manipulo blanco", 37, 1, 14, 10, 0, 0, A), ("HOCA-004", "Lateral negro Ledmanipulo", 222, 2, 176, 20, 1, 46, A),
    ("HOCA-005", "Reflector blanco manipulo", 312, 1, 289, 10, 1, 23, A), ("HOCA-006", "Botones", 348, 1, 325, 10, 1, 23, A),
    ("HOCA-007", "Cable-tail", 170, 1, 147, 10, 0, 0, A), ("HOCA-008", "Chapas", 569, 2, 523, 20, 0, 0, A),
    ("HOCA-009", "Placa transductor", 43, 1, 20, 10, 1, 52, C), ("HOCA-010", "Placa leds", 42, 1, 19, 10, 1, 44, C),
    ("HOCA-011", "Cable manipulo", 68, 1, 45, 10, 1, 23, C), ("HOCA-012", "Sensor temperatura", 107, 4, 15, 40, 0, 0, C),
    ("HOCA-013", "Cuerpo manipulo gris", 32, 1, 27, 10, 0, 0, C), ("HOCA-014", "Anillo manipulo gris", 119, 1, 114, 10, 0, 0, C),
    ("HOCA-015", "Tornillos", 140, 4, 48, 40, 1, 264, S), ("HOCA-016", "Transductores", 73, 1, 50, 10, 1, 66, S),
    ("HOCA-017", "Transductor Facial", 20, 1, 15, 10, 1, 0, S), ("HOCA-018", "Volcan Facial", 15, 1, 15, 10, 0, 0, A),
    ("HOCA-019", "Placa Facial", 0, 1, 0, 10, 1, 0, C),
]

CONTADORES = [
    ("ocarina", "ocarines_acabadas", "Ocarines acabadas", 6),
    ("ocarina", "oc_int_fin", "Oc. internacional fin", 8),
    ("manipulo", "manipulos_terminados", "Manípulos terminados", 23),
    ("manipulo", "manipulos_inter", "Manípulos inter.", 5),
    ("manipulo", "manipulos_reutilizables", "Manípulos reutilizables (funcionales)", 23),
    ("manipulo", "manipulos_devueltos", "Manípulos devueltos", 43),
    ("manipulo", "manipulos_enviados", "Manípulos enviados", 101),
]


class Command(BaseCommand):
    help = "Carga los datos iniciales. Solo crea lo que no existe (no pisa cambios)."

    def handle(self, *args, **opts):
        for c, n, i, x, r, ideal, q in OCARINAS:
            PiezaOcarina.objects.get_or_create(codigo=c, defaults=dict(
                nombre=n, inicial=i, por_unidad=x, restante=r, ideal=ideal, quien=q))
        for c, n, i, x, r, ideal, re, rc, q in MANIPULOS:
            PiezaManipulo.objects.get_or_create(codigo=c, defaults=dict(
                nombre=n, inicial=i, por_unidad=x, restante=r, ideal=ideal,
                reutilizables=bool(re), reciclados=rc, quien=q))
        for g, k, e, v in CONTADORES:
            Contador.objects.get_or_create(clave=k, defaults=dict(grupo=g, etiqueta=e, valor=v))
        self.stdout.write(self.style.SUCCESS("Datos cargados"))
