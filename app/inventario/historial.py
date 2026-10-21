from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from .models import Movimiento
from .views import TABLAS, api, err, es_admin, mov, puede_rapida

HORAS = 24
DESHACER = {"rapida", "montaje", "reciclaje"}
TIPOS = {
    "rapida": ("Ajuste", "azul"),
    "montaje": ("Montaje", "verde"),
    "reciclaje": ("Reciclaje", "verde"),
    "avanzada": ("Edición avanzada", "gris"),
    "alta": ("Alta de pieza", "gris"),
    "baja": ("Baja de pieza", "rojo"),
    "deshacer": ("Deshacer", "rojo"),
}
SECCIONES = {"ocarina": "Ocarines", "manipulo": "Manípulos"}


def _seccion(movs):
    for m in movs:
        if m.tabla in SECCIONES:
            return SECCIONES[m.tabla]
    return "Manípulos" if movs[0].codigo.startswith("manipulos") else "Ocarines"


def _resumen(tipo, movs):
    m = movs[0]
    if tipo == "rapida":
        d = (m.nuevo or 0) - (m.anterior or 0)
        return f"{m.codigo}: {m.anterior} -> {m.nuevo} ({d:+d})"
    if tipo == "montaje":
        piezas = [x for x in movs if x.tabla != "contador"]
        return f"{m.detalle} ({len(piezas)} piezas descontadas)"
    if tipo == "reciclaje":
        total = sum((x.nuevo or 0) - (x.anterior or 0) for x in movs)
        return f"{len(movs)} piezas recuperadas ({total} unidades)"
    if tipo == "deshacer":
        return f"Se deshizo una operación ({len(movs)} registros)"
    return f"{m.codigo}: {m.detalle}" if m.detalle else m.codigo


def _puede(user, tipo, movs, revertido):
    if tipo not in DESHACER or not movs[0].lote or revertido:
        return False
    if user.is_superuser:
        return True
    if not puede_rapida(user):
        return False
    if any(m.usuario_id != user.id for m in movs):
        return False
    return timezone.now() - movs[0].fecha <= timedelta(hours=HORAS)


def _operaciones(user, limite=300):
    grupos = {}
    for m in Movimiento.objects.select_related("usuario").order_by("-fecha", "-pk")[:2000]:
        clave = str(m.lote) if m.lote else f"m{m.pk}"
        if clave not in grupos:
            if len(grupos) >= limite:
                continue
            grupos[clave] = []
        grupos[clave].append(m)
    ops = []
    for movs in grupos.values():
        movs.reverse()
        m = movs[0]
        tipo = m.tipo
        etiqueta, color = TIPOS.get(tipo, (tipo, "gris"))
        revertido = any(x.revertido for x in movs)
        usuario = m.usuario.username if m.usuario else "(borrado)"
        resumen = _resumen(tipo, movs)
        ops.append({
            "lote": m.lote, "fecha": m.fecha, "usuario": usuario, "tipo": tipo,
            "etiqueta": etiqueta, "color": color, "seccion": _seccion(movs),
            "resumen": resumen, "revertido": revertido,
            "movs": [(x.codigo, x.anterior, x.nuevo) for x in movs],
            "puede": _puede(user, tipo, movs, revertido),
            "q": f"{usuario} {resumen} {' '.join(x.codigo for x in movs)}".lower(),
        })
    return ops


@login_required
def historial(request):
    ops = _operaciones(request.user)
    return render(request, "inventario/historial.html", {
        "ops": ops, "seccion": "historial", "limite": HORAS,
        "es_admin": es_admin(request.user),
        "tipos": [(k, v[0]) for k, v in TIPOS.items()],
        "usuarios": sorted({o["usuario"] for o in ops}),
    })


@api(puede_rapida)
def deshacer(request, body, lote):
    with transaction.atomic():
        movs = list(Movimiento.objects.select_for_update().filter(lote=lote).order_by("pk"))
        if not movs:
            return err("No se encontró la operación.", 404)
        if any(m.revertido for m in movs):
            return err("Esta operación ya se deshizo.", 409)
        if any(m.tipo not in DESHACER for m in movs):
            return err("Este tipo de operación no se puede deshacer.")
        if not request.user.is_superuser:
            if any(m.usuario_id != request.user.id for m in movs):
                return err("Solo puedes deshacer tus propias operaciones.", 403)
            if timezone.now() - movs[0].fecha > timedelta(hours=HORAS):
                return err(f"Solo se puede deshacer durante las primeras {HORAS} horas.", 403)

        plan = []                                   # primero validar todo
        for m in movs:
            M = TABLAS[m.tabla]
            filtro = {"clave": m.codigo} if m.tabla == "contador" else {"codigo": m.codigo}
            try:
                obj = M.objects.select_for_update().get(**filtro)
            except M.DoesNotExist:
                return err(f"{m.codigo} ya no existe, no se puede deshacer.", 409)
            d = (m.nuevo or 0) - (m.anterior or 0)
            campo = M.CAMPO_RAPIDO
            actual = getattr(obj, campo)
            nuevo = actual - d
            if m.tabla == "contador" and nuevo < 0:
                return err(f"{m.codigo} quedaría por debajo de 0, no se puede deshacer.", 409)
            recic = None
            if m.tipo == "reciclaje" and m.tabla == "manipulo":
                recic = obj.reciclados - d
                if recic < 0:
                    return err(f"{m.codigo}: los reciclados quedarían negativos.", 409)
            plan.append((m, obj, campo, actual, nuevo, recic))

        for m, obj, campo, actual, nuevo, recic in plan:   # luego aplicar
            setattr(obj, campo, nuevo)
            campos = [campo, "version", "updated_at"]
            if recic is not None:
                obj.reciclados = recic
                campos.append("reciclados")
            obj.version += 1
            obj.save(update_fields=campos)
            mov(request, tabla=m.tabla, codigo=m.codigo, tipo="deshacer",
                anterior=actual, nuevo=nuevo,
                detalle="Deshace operación del " + timezone.localtime(m.fecha).strftime("%d/%m/%Y %H:%M"))
        Movimiento.objects.filter(pk__in=[m.pk for m in movs]).update(revertido=True)
    return JsonResponse({"ok": True})
