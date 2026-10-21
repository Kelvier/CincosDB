import json
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.forms import modelform_factory
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import formats

from .models import QUIEN, Contador, Movimiento, PiezaManipulo, PiezaOcarina

TABLAS = {"ocarina": PiezaOcarina, "manipulo": PiezaManipulo, "contador": Contador}

PAGINAS = {
    "ocarina": {
        "titulo": "Inventario Cincos · Ocarinas",
        "tarjetas": [("c", "ocarines_acabadas"), ("calc", "maquinas_posibles", "Máquinas posibles"),
                     ("c", "oc_int_fin"), ("calc", "inter_posibles", "Inter. posibles")],
    },
    "manipulo": {
        "titulo": "Manípulos",
        "tarjetas": [("c", "manipulos_terminados"), ("c", "manipulos_inter"),
                     ("c", "manipulos_reutilizables"), ("c", "manipulos_devueltos"),
                     ("c", "manipulos_enviados"), ("calc", "en_servicio", "Manípulos en servicio")],
    },
}


# ---------- permisos ----------
def es_admin(u):
    return u.is_authenticated and u.is_superuser


def puede_rapida(u):
    return u.is_authenticated and (u.is_superuser or u.groups.filter(name="Operario").exists())


# ---------- utilidades ----------
def modelo(tabla):
    try:
        return TABLAS[tabla]
    except KeyError:
        raise Http404


def texto(v):
    if isinstance(v, bool):
        return "Sí" if v else ""
    if isinstance(v, int):
        return formats.number_format(v, force_grouping=True)
    return str(v)


def fila(obj):
    datos = {c: getattr(obj, c) for c in obj.CAMPOS_FORM}
    return {"pk": obj.pk, "version": obj.version, "bajo": obj.bajo,
            "datos": datos, "texto": {c: texto(v) for c, v in datos.items()}}


def resumen(grupo):
    if grupo == "ocarina":
        ratios = [p.restante / p.por_unidad for p in PiezaOcarina.objects.filter(por_unidad__gt=0)]
        m = formats.number_format(round(min(ratios), 1), decimal_pos=1) if ratios else "0"
        return {"maquinas_posibles": m, "inter_posibles": m}
    c = dict(Contador.objects.filter(grupo="manipulo").values_list("clave", "valor"))
    return {"en_servicio": texto(c.get("manipulos_enviados", 0) - c.get("manipulos_devueltos", 0))}


def campos_meta(M):
    out = []
    for n in M.CAMPOS_FORM:
        f = M._meta.get_field(n)
        if isinstance(f, models.BooleanField):
            t = "bool"
        elif f.choices:
            t = "select"
        elif isinstance(f, models.CharField):
            t = "text"
        else:
            t = "number"
        out.append({"name": n, "label": str(f.verbose_name), "type": t,
                    "choices": [c[0] for c in f.choices] if f.choices else []})
    return out


def codigo_de(obj):
    return getattr(obj, "codigo", None) or obj.clave


def grupo_de(tabla, obj):
    return obj.grupo if tabla == "contador" else tabla


def errores(form):
    return " | ".join(f"{form.fields[k].label if k in form.fields else k}: {' '.join(v)}"
                      for k, v in form.errors.items())


def err(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def api(permiso):
    def deco(fn):
        @wraps(fn)
        def inner(request, *a, **kw):
            if request.method != "POST":
                return err("Método no permitido.", 405)
            if not request.user.is_authenticated:
                return err("Sesión caducada. Recarga la página y entra de nuevo.", 401)
            if not permiso(request.user):
                return err("No tienes permiso para esta acción.", 403)
            try:
                body = json.loads(request.body or "{}")
            except ValueError:
                return err("Datos no válidos.")
            return fn(request, body, *a, **kw)
        return inner
    return deco


# ---------- página ----------
@login_required
def pagina(request, tabla):
    cfg = PAGINAS[tabla]
    M = modelo(tabla)
    columnas = [(c, "Poco material" if c == "estado" else str(M._meta.get_field(c).verbose_name))
                for c in M.COLUMNAS]
    filas = []
    for o in M.objects.all():
        f = fila(o)
        filas.append({"pk": o.pk, "bajo": o.bajo, "json": json.dumps(f),
                      "q": f"{o.codigo} {o.nombre}".lower(), "quien": o.quien,
                      "celdas": [(c, f["texto"].get(c, "")) for c in M.COLUMNAS]})
    cont = {c.clave: c for c in Contador.objects.filter(grupo=tabla)}
    res = resumen(tabla)
    tarjetas = []
    for t in cfg["tarjetas"]:
        if t[0] == "c" and t[1] in cont:
            c = cont[t[1]]
            f = fila(c)
            tarjetas.append({"etiqueta": c.etiqueta, "pk": c.pk, "texto": f["texto"]["valor"],
                             "json": json.dumps(f)})
        elif t[0] == "calc":
            tarjetas.append({"etiqueta": t[2], "calc": t[1], "texto": res[t[1]]})
    return render(request, "inventario/tabla.html", {
        "titulo": cfg["titulo"], "tabla": tabla, "columnas": columnas, "filas": filas,
        "tarjetas": tarjetas, "quienes": [q[0] for q in QUIEN],
        "meta": campos_meta(M), "meta_contador": campos_meta(Contador),
        "es_admin": es_admin(request.user), "puede_rapida": puede_rapida(request.user),
    })


# ---------- API ----------
@api(puede_rapida)
def ajustar(request, body, tabla, pk):
    M = modelo(tabla)
    try:
        delta = int(body.get("delta"))
    except (TypeError, ValueError):
        return err("Cantidad no válida.")
    if delta == 0 or abs(delta) > 1_000_000:
        return err("Cantidad no válida.")
    with transaction.atomic():
        try:
            obj = M.objects.select_for_update().get(pk=pk)
        except M.DoesNotExist:
            return err("El registro ya no existe. Recarga la página.", 404)
        campo = M.CAMPO_RAPIDO
        ant = getattr(obj, campo)
        nuevo = ant + delta
        if tabla == "contador" and nuevo < 0:
            return err("No puede quedar por debajo de 0.")
        setattr(obj, campo, nuevo)
        obj.version += 1
        obj.save(update_fields=[campo, "version", "updated_at"])
        Movimiento.objects.create(usuario=request.user, tabla=tabla, codigo=codigo_de(obj),
                                  tipo="rapida", anterior=ant, nuevo=nuevo, detalle=campo)
    return JsonResponse({"fila": fila(obj), "resumen": resumen(grupo_de(tabla, obj))})


@api(es_admin)
def editar(request, body, tabla, pk):
    M = modelo(tabla)
    Form = modelform_factory(M, fields=M.CAMPOS_FORM)
    with transaction.atomic():
        try:
            obj = M.objects.select_for_update().get(pk=pk)
        except M.DoesNotExist:
            return err("El registro ya no existe. Recarga la página.", 404)
        if body.get("version") != obj.version:
            return err("Otra persona modificó este registro mientras lo editabas. "
                       "Cierra esta ventana, recarga la página y vuelve a intentarlo.", 409)
        antes = {c: getattr(obj, c) for c in M.CAMPOS_FORM}
        form = Form(body.get("datos", {}), instance=obj)
        if not form.is_valid():
            return err(errores(form))
        obj = form.save(commit=False)
        obj.version += 1
        obj.save()
        cambios = "; ".join(f"{c}: {antes[c]}  {getattr(obj, c)}"
                            for c in antes if antes[c] != getattr(obj, c))
        Movimiento.objects.create(usuario=request.user, tabla=tabla, codigo=codigo_de(obj),
                                  tipo="avanzada", detalle=cambios)
    return JsonResponse({"fila": fila(obj), "resumen": resumen(grupo_de(tabla, obj))})


@api(es_admin)
def nuevo(request, body, tabla):
    M = modelo(tabla)
    if M is Contador:
        raise Http404
    form = modelform_factory(M, fields=M.CAMPOS_FORM)(body.get("datos", {}))
    if not form.is_valid():
        return err(errores(form))
    with transaction.atomic():
        obj = form.save()
        Movimiento.objects.create(usuario=request.user, tabla=tabla, codigo=obj.codigo,
                                  tipo="alta", detalle=obj.nombre)
    return JsonResponse({"ok": True})


@api(es_admin)
def borrar(request, body, tabla, pk):
    M = modelo(tabla)
    if M is Contador:
        raise Http404
    with transaction.atomic():
        try:
            obj = M.objects.select_for_update().get(pk=pk)
        except M.DoesNotExist:
            return err("El registro ya no existe.", 404)
        Movimiento.objects.create(usuario=request.user, tabla=tabla, codigo=obj.codigo,
                                  tipo="baja", detalle=f"{obj.nombre} (restante {obj.restante})")
        obj.delete()
    return JsonResponse({"ok": True})
