from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.shortcuts import render

from .models import PiezaManipulo, PiezaOcarina


@login_required
def faltas(request):
    secciones = []
    for titulo, M in (("Ocarines", PiezaOcarina), ("Manípulos", PiezaManipulo)):
        piezas = list(M.objects.filter(restante__lt=F("ideal")).order_by("restante", "codigo"))
        secciones.append({"titulo": titulo, "piezas": piezas, "total": len(piezas)})
    return render(request, "inventario/faltas.html", {"secciones": secciones, "seccion": "faltas"})
