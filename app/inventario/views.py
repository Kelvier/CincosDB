import json
import uuid
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.forms import modelform_factory
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from django.utils import formats, timezone

from .models import (OC_VARIANTES, QUIEN, VARIANTES, Contador, InformeAveria, Movimiento,
                     PiezaInformeAveria, PiezaManipulo, PiezaOcarina, Uso, UsoOcarina)

from .models import ORIGENES_PIEZA_AVERIA

TABLAS = {"ocarina": PiezaOcarina, "manipulo": PiezaManipulo, "contador": Contador}
USOS = {"ocarina": UsoOcarina, "manipulo": Uso}
USO_DE = {PiezaOcarina: UsoOcarina, PiezaManipulo: Uso}
LISTA_VAR = {"ocarina": OC_VARIANTES, "manipulo": VARIANTES}
VARS = {t: dict(v) for t, v in LISTA_VAR.items()}
CONTADOR_MONTAJE = {
    "ocarina:nacional": "ocarines_acabadas", "ocarina:internacional": "oc_int_fin",
    "manipulo:nacional": "manipulos_terminados", "manipulo:internacional": "manipulos_inter",
    "manipulo:facial": "manipulos_facial",
}
CALC_OC = {"nacional": ("maquinas_posibles", "Máquinas posibles"),
           "internacional": ("inter_posibles", "Inter. posibles")}
COMPARTIDOS = [("c", "manipulos_reutilizables"), ("c", "manipulos_devueltos"),
               ("c", "manipulos_enviados"), ("calc", "en_servicio", "Manípulos en servicio")]

PAGINAS = {
    "ocarina": {
        "titulo": "Inventario Cincos - Ocarine", "seccion": "Ocarines",
        "unidad": "máquina", "unidades": "máquinas",
        "ruta": "ocarines", "ruta_var": "ocarina_var", "icono": "\U0001F5A5\uFE0F",
        "desc": "Piezas y materiales de las máquinas ocarine.",
        "sub": "Elige el tipo de ocarine con el que quieres trabajar.",
        "desc_var": {"nacional": "Plásticos exteriores blancos.",
                     "internacional": "Plásticos exteriores grises."},
    },
    "manipulo": {
        "titulo": "Inventario - Manípulo", "seccion": "Manípulos",
        "unidad": "manípulo", "unidades": "manípulos",
        "ruta": "manipulos", "ruta_var": "manipulo_var", "icono": "\U0001F579\uFE0F",
        "desc": "Nacional, internacional y facial.",
        "sub": "Elige el tipo de manípulo con el que quieres trabajar.",
        "desc_var": {"nacional": "Plásticos blancos.", "internacional": "Plásticos grises.",
                     "facial": "Placa, volcán y transductor facial. Solo 2 sensores de temperatura."},
    },
}


def mov(request, **datos):
    """Un mismo request = una misma operacion (lote), para poder deshacerla entera."""
    if not hasattr(request, "_lote"):
        request._lote = uuid.uuid4()
    return Movimiento.objects.create(lote=request._lote, usuario=request.user, **datos)


# ---------- permisos ----------
def es_admin(u):
    return u.is_authenticated and u.is_superuser


def puede_rapida(u):
    return u.is_authenticated and (u.is_superuser or u.groups.filter(name="Operario").exists())

def puede_modificar_inventario(u):
    return u.is_authenticated


# ---------- utilidades ----------
def modelo(tabla):
    try:
        return TABLAS[tabla]
    except KeyError:
        raise Http404


def var_de(body, tabla):
    if tabla not in VARS:
        return None
    v = body.get("variante")
    return v if v in VARS[tabla] else None


def texto(v):
    if isinstance(v, bool):
        return "Sí" if v else "-"
    if isinstance(v, int):
        return formats.number_format(v, force_grouping=True)
    return str(v)


def fila(obj, var=None, cant=None):
    datos = {c: getattr(obj, c) for c in obj.CAMPOS_FORM}
    uso = USO_DE.get(type(obj))
    if var and uso:
        if cant is None:
            u = uso.objects.filter(pieza=obj, variante=var).first()
            cant = u.cantidad if u else 0
        datos["por_unidad"] = cant
    return {"pk": obj.pk, "version": obj.version, "bajo": obj.bajo,
            "datos": datos, "texto": {c: texto(v) for c, v in datos.items()}}


def resumen(grupo):
    if grupo == "ocarina":
        out = {}
        for var, (clave, _) in CALC_OC.items():
            ratios = [u.pieza.restante / u.cantidad for u in
                      UsoOcarina.objects.filter(variante=var, cantidad__gt=0).select_related("pieza")]
            out[clave] = formats.number_format(round(min(ratios), 1), decimal_pos=1) if ratios else "0"
        return out
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


def _n(body, maximo=1000):
    try:
        n = int(body.get("n", 1))
    except (TypeError, ValueError):
        return None
    return n if 1 <= n <= maximo else None


# ---------- páginas ----------
@login_required
def inicio(request):
    tiles = []
    for clave in ("ocarina", "manipulo"):
        cfg = PAGINAS[clave]
        piezas = list(modelo(clave).objects.all())
        tiles.append({"clave": clave, "url": cfg["ruta"], "icono": cfg["icono"], "desc": cfg["desc"],
                      "titulo": cfg["seccion"], "total": len(piezas),
                      "bajos": sum(1 for p in piezas if p.bajo)})
    return render(request, "inventario/home.html", {
        "tiles": tiles, "seccion": "inicio", "es_admin": es_admin(request.user)})


@login_required
def menu_variantes(request, tabla):
    cfg = PAGINAS[tabla]
    tiles = []
    for clave, nombre in LISTA_VAR[tabla]:
        piezas = [u.pieza for u in USOS[tabla].objects.filter(variante=clave).select_related("pieza")]
        c = Contador.objects.filter(clave=CONTADOR_MONTAJE[f"{tabla}:{clave}"]).first()
        tiles.append({"clave": clave, "nombre": nombre, "letra": nombre[0],
                      "desc": cfg["desc_var"][clave], "total": len(piezas),
                      "bajos": sum(1 for p in piezas if p.bajo), "hechos": c.valor if c else 0,
                      "href": reverse(cfg["ruta_var"], args=[clave])})
    return render(request, "inventario/manipulos_menu.html", {
        "tiles": tiles, "seccion": tabla, "titulo": cfg["seccion"], "subtitulo": cfg["sub"]})


@login_required
def pagina(request, tabla, variante=None):
    cfg = PAGINAS[tabla]
    M = modelo(tabla)
    if variante not in VARS[tabla]:
        raise Http404
    usos = {u.pieza_id: u.cantidad for u in USOS[tabla].objects.filter(variante=variante)}
    qs = M.objects.filter(pk__in=list(usos))
    nombre_var = VARS[tabla][variante]
    titulo = f"{cfg['titulo']} {nombre_var.lower()}"
    clave_c = CONTADOR_MONTAJE[f"{tabla}:{variante}"]
    if tabla == "ocarina":
        defs = [("c", clave_c), ("calc") + CALC_OC[variante]] if False else \
               [("c", clave_c), ("calc", *CALC_OC[variante])]
    else:
        defs = [("c", clave_c)] + COMPARTIDOS
    columnas = [(c, "Poco material" if c == "estado" else str(M._meta.get_field(c).verbose_name))
                for c in M.COLUMNAS]
    filas = []
    for o in qs:
        f = fila(o, variante, usos.get(o.pk))
        filas.append({"pk": o.pk, "bajo": o.bajo, "json": json.dumps(f),
                      "q": f"{o.codigo} {o.nombre}".lower(), "quien": o.quien,
                      "celdas": [(c, f["texto"].get(c, "")) for c in M.COLUMNAS]})
    cont = {c.clave: c for c in Contador.objects.filter(grupo=tabla)}
    res = resumen(tabla)
    tarjetas = []
    for t in defs:
        if t[0] == "c" and t[1] in cont:
            c = cont[t[1]]
            f = fila(c)
            tarjetas.append({"etiqueta": c.etiqueta, "pk": c.pk, "texto": f["texto"]["valor"],
                             "json": json.dumps(f)})
        elif t[0] == "calc":
            tarjetas.append({"etiqueta": t[2], "calc": t[1], "texto": res[t[1]]})
    return render(request, "inventario/tabla.html", {
        "titulo": titulo, "tabla": tabla, "seccion": tabla,
        "variante": variante, "nombre_variante": nombre_var, "url_menu": reverse(cfg["ruta"]),
        "nombre_seccion": cfg["seccion"], "unidad": cfg["unidad"], "unidades": cfg["unidades"],
        "columnas": columnas, "filas": filas,
        "tarjetas": tarjetas, "quienes": [q[0] for q in QUIEN],
        "meta": campos_meta(M), "meta_contador": campos_meta(Contador),
        "es_admin": es_admin(request.user), "puede_rapida": puede_rapida(request.user),
        "puede_modificar_inventario": puede_modificar_inventario(request.user),
        "informes_pendientes": InformeAveria.objects.filter(tabla=tabla, variante=variante, estado="pendiente").select_related("creado_por").order_by("-creado_en"),
        "informes_completados": InformeAveria.objects.filter(tabla=tabla, variante=variante, estado="completada").select_related("creado_por", "reparado_por").order_by("-completado_en")[:10],
    })


# ---------- API ----------
@api(puede_modificar_inventario)
def ajustar(request, body, tabla, pk):
    M = modelo(tabla)
    var = var_de(body, tabla)
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
        mov(request, tabla=tabla, codigo=codigo_de(obj), tipo="rapida",
            anterior=ant, nuevo=nuevo, detalle=campo)
    return JsonResponse({"fila": fila(obj, var), "resumen": resumen(grupo_de(tabla, obj))})


@api(puede_rapida)
def montar(request, body, tabla):
    M = modelo(tabla)
    if M is Contador:
        raise Http404
    var = var_de(body, tabla)
    if not var:
        return err("Elige un tipo.")
    n = _n(body)
    if n is None:
        return err("Cantidad no válida.")
    forzar = bool(body.get("forzar")) and request.user.is_superuser
    nombre = f" ({VARS[tabla][var]})"
    with transaction.atomic():
        cants = {u.pieza_id: u.cantidad for u in USOS[tabla].objects.filter(variante=var, cantidad__gt=0)}
        piezas = list(M.objects.select_for_update().filter(pk__in=list(cants)).order_by("pk"))
        if not piezas:
            return err("Este tipo todavía no tiene piezas configuradas.")
        faltan = [p for p in piezas if p.restante < cants[p.pk] * n]
        if faltan and not forzar:
            lista = ", ".join(f"{p.nombre} (hay {p.restante}, hacen falta {cants[p.pk] * n})"
                              for p in faltan[:5])
            extra = f" y {len(faltan) - 5} más" if len(faltan) > 5 else ""
            return err(f"No hay material suficiente: {lista}{extra}.", 409)
        for p in piezas:
            ant = p.restante
            p.restante = ant - cants[p.pk] * n
            p.version += 1
            p.save(update_fields=["restante", "version", "updated_at"])
            mov(request, tabla=tabla, codigo=p.codigo, tipo="montaje",
                anterior=ant, nuevo=p.restante, detalle=f"Montaje de {n}{nombre}")
        c = Contador.objects.select_for_update().filter(clave=CONTADOR_MONTAJE[f"{tabla}:{var}"]).first()
        if c:
            ant = c.valor
            c.valor += n
            c.version += 1
            c.save(update_fields=["valor", "version", "updated_at"])
            mov(request, tabla="contador", codigo=c.clave, tipo="montaje",
                anterior=ant, nuevo=c.valor, detalle=f"Montaje de {n}{nombre}")
    return JsonResponse({"filas": [fila(p, var, cants[p.pk]) for p in piezas],
                         "contador": fila(c) if c else None, "resumen": resumen(tabla)})


@api(puede_rapida)
def reciclar(request, body, tabla):
    M = modelo(tabla)
    if M is Contador:
        raise Http404
    var = var_de(body, tabla)
    if not var:
        return err("Elige un tipo.")
    n = _n(body)
    if n is None:
        return err("Cantidad no válida.")
    try:
        items = {int(k): int(v) for k, v in (body.get("items") or {}).items() if int(v) > 0}
    except (TypeError, ValueError, AttributeError):
        return err("Datos no válidos.")
    if not items:
        return err("No has marcado ninguna pieza recuperada.")
    nombre = f" ({VARS[tabla][var]})"
    with transaction.atomic():
        piezas = {p.pk: p for p in M.objects.select_for_update().filter(pk__in=list(items)).order_by("pk")}
        if len(piezas) != len(items):
            return err("Alguna pieza ya no existe. Recarga la página.", 404)
        cants = {u.pieza_id: u.cantidad for u in
                 USOS[tabla].objects.filter(variante=var, pieza_id__in=list(items))}
        for pk, q in items.items():           # primero validar todo
            p = piezas[pk]
            maximo = cants.get(pk, 0) * n
            if q > maximo:
                return err(f"{p.nombre}: el máximo recuperable es {maximo}.")
        for pk in sorted(items):              # luego aplicar
            p, q = piezas[pk], items[pk]
            ant = p.restante
            p.restante = ant + q
            campos = ["restante", "version", "updated_at"]
            if tabla == "manipulo":
                p.reciclados += q
                campos.append("reciclados")
            p.version += 1
            p.save(update_fields=campos)
            mov(request, tabla=tabla, codigo=p.codigo, tipo="reciclaje",
                anterior=ant, nuevo=p.restante, detalle=f"+{q} recuperadas de {n}{nombre}")
    return JsonResponse({"filas": [fila(p, var, cants.get(p.pk)) for p in piezas.values()],
                         "resumen": resumen(tabla)})


@api(es_admin)
def editar(request, body, tabla, pk):
    M = modelo(tabla)
    var = var_de(body, tabla)
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
        base = obj.por_unidad if var else None
        if var:
            uso = USOS[tabla].objects.filter(pieza=obj, variante=var).first()
            antes["por_unidad"] = uso.cantidad if uso else 0
        form = Form(body.get("datos", {}), instance=obj)
        if not form.is_valid():
            return err(errores(form))
        obj = form.save(commit=False)
        despues = {c: getattr(obj, c) for c in M.CAMPOS_FORM}
        if var:
            obj.por_unidad = base          # el "x unidad" se guarda por tipo, no en la pieza
            USOS[tabla].objects.update_or_create(pieza=obj, variante=var,
                                                 defaults={"cantidad": despues["por_unidad"]})
        obj.version += 1
        obj.save()
        cambios = "; ".join(f"{c}: {antes[c]} -> {despues[c]}" for c in antes if antes[c] != despues[c])
        mov(request, tabla=tabla, codigo=codigo_de(obj), tipo="avanzada",
            detalle=(f"[{VARS[tabla][var]}] " if var else "") + cambios)
    return JsonResponse({"fila": fila(obj, var, despues["por_unidad"] if var else None),
                         "resumen": resumen(grupo_de(tabla, obj))})


@api(es_admin)
def nuevo(request, body, tabla):
    M = modelo(tabla)
    if M is Contador:
        raise Http404
    var = var_de(body, tabla)
    if not var:
        return err("Elige un tipo.")
    form = modelform_factory(M, fields=M.CAMPOS_FORM)(body.get("datos", {}))
    if not form.is_valid():
        return err(errores(form))
    with transaction.atomic():
        obj = form.save()
        USOS[tabla].objects.create(pieza=obj, variante=var, cantidad=obj.por_unidad)
        mov(request, tabla=tabla, codigo=obj.codigo, tipo="alta",
            detalle=f"{obj.nombre} [{VARS[tabla][var]}]")
    return JsonResponse({"ok": True})


@api(es_admin)
def borrar(request, body, tabla, pk):
    M = modelo(tabla)
    if M is Contador:
        raise Http404
    var = var_de(body, tabla)
    with transaction.atomic():
        try:
            obj = M.objects.select_for_update().get(pk=pk)
        except M.DoesNotExist:
            return err("El registro ya no existe.", 404)
        if var:
            USOS[tabla].objects.filter(pieza=obj, variante=var).delete()
            if obj.usos.exists():              # la usa otro tipo: solo se quita de este
                mov(request, tabla=tabla, codigo=obj.codigo, tipo="baja",
                    detalle=f"{obj.nombre} quitada de {VARS[tabla][var]}")
                return JsonResponse({"ok": True})
        mov(request, tabla=tabla, codigo=obj.codigo, tipo="baja",
            detalle=f"{obj.nombre} (restante {obj.restante})")
        obj.delete()
    return JsonResponse({"ok": True})

# ---------- Informes de avería ----------
def _contexto_informe_averia(informe, lineas_formulario=None, error="", reparacion_form=None):
    M = modelo(informe.tabla)
    uso_modelo = USOS[informe.tabla]
    ids = uso_modelo.objects.filter(variante=informe.variante, cantidad__gt=0).values_list("pieza_id", flat=True)
    piezas_disponibles = M.objects.filter(pk__in=ids).order_by("codigo")
    if lineas_formulario is None:
        lineas_formulario = [{"pieza": "", "cantidad": "", "origen": "nueva"}]
    if not lineas_formulario:
        lineas_formulario = [{"pieza": "", "cantidad": "", "origen": "nueva"}]
    cfg = PAGINAS[informe.tabla]
    if informe.tabla == "ocarina":
        volver_url = reverse("ocarina_var", args=[informe.variante])
    else:
        volver_url = reverse("manipulo_var", args=[informe.variante])
    return {
        "informe": informe,
        "piezas_disponibles": piezas_disponibles,
        "lineas_formulario": lineas_formulario,
        "error": error,
        "reparacion_form": informe.reparacion_realizada if reparacion_form is None else reparacion_form,
        "nombre_variante": VARS[informe.tabla].get(informe.variante, informe.variante),
        "nombre_seccion": cfg["seccion"],
        "volver_url": volver_url,
        "seccion": informe.tabla,
    }


@api(puede_modificar_inventario)
def crear_averia(request, body):
    tabla = body.get("tabla")
    variante = body.get("variante")
    if tabla not in PAGINAS or variante not in VARS.get(tabla, {}):
        return err("Selecciona un equipo y un modelo válidos.")
    numero_serie = str(body.get("numero_serie", "")).strip()
    descripcion = str(body.get("descripcion_averia", "")).strip()
    if not numero_serie:
        return err("El número de serie es obligatorio.")
    if len(numero_serie) > 100:
        return err("El número de serie no puede superar los 100 caracteres.")
    if not descripcion:
        return err("Describe la avería antes de guardar el informe.")
    informe = InformeAveria.objects.create(
        tabla=tabla, variante=variante, numero_serie=numero_serie,
        descripcion_averia=descripcion, creado_por=request.user,
    )
    return JsonResponse({"ok": True, "id": informe.pk,
                         "mensaje": "Informe guardado como pendiente de reparación."}, status=201)


def averia_detalle(request, pk):
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")
    informe = get_object_or_404(
        InformeAveria.objects.select_related("creado_por", "reparado_por").prefetch_related("piezas"), pk=pk
    )
    if request.method == "GET":
        return render(request, "inventario/averia_detalle.html", _contexto_informe_averia(informe))

    if informe.estado != "pendiente":
        return render(request, "inventario/averia_detalle.html",
                      _contexto_informe_averia(informe, error="Este informe ya ha sido completado."), status=409)

    reparacion = request.POST.get("reparacion_realizada", "").strip()
    ids_post = request.POST.getlist("pieza")
    cantidades_post = request.POST.getlist("cantidad")
    origenes_post = request.POST.getlist("origen")
    filas = []
    errores_form = []
    for i in range(max(len(ids_post), len(cantidades_post), len(origenes_post))):
        pieza_id = ids_post[i].strip() if i < len(ids_post) else ""
        cantidad_txt = cantidades_post[i].strip() if i < len(cantidades_post) else ""
        origen = origenes_post[i].strip() if i < len(origenes_post) else "nueva"
        if not pieza_id and not cantidad_txt:
            continue
        if not pieza_id:
            errores_form.append(f"Fila {i + 1}: selecciona una pieza.")
            continue
        try:
            pieza_id_int = int(pieza_id)
            cantidad = int(cantidad_txt)
        except (TypeError, ValueError):
            errores_form.append(f"Fila {i + 1}: selecciona una pieza y una cantidad válida.")
            continue
        if cantidad < 1 or cantidad > 100000:
            errores_form.append(f"Fila {i + 1}: la cantidad debe estar entre 1 y 100.000.")
            continue
        if origen not in dict(ORIGENES_PIEZA_AVERIA):
            errores_form.append(f"Fila {i + 1}: el origen de la pieza no es válido.")
            continue
        filas.append({"pieza": pieza_id_int, "cantidad": cantidad, "origen": origen})

    if not reparacion:
        errores_form.append("Describe la reparación realizada.")
    if errores_form:
        return render(request, "inventario/averia_detalle.html",
                      _contexto_informe_averia(informe, _filas_formulario(ids_post, cantidades_post, origenes_post),
                                               " ".join(errores_form), reparacion), status=400)

    error = ""
    informe_id = informe.pk
    with transaction.atomic():
        informe = InformeAveria.objects.select_for_update().get(pk=informe_id)
        if informe.estado != "pendiente":
            error = "Otra persona ya ha completado este informe. Recarga la página para ver el resultado."
        else:
            M = modelo(informe.tabla)
            uso_modelo = USOS[informe.tabla]
            ids_permitidos = set(uso_modelo.objects.filter(
                variante=informe.variante, cantidad__gt=0
            ).values_list("pieza_id", flat=True))
            ids_solicitados = {fila["pieza"] for fila in filas}
            if not ids_solicitados.issubset(ids_permitidos):
                error = "Una de las piezas no pertenece al modelo seleccionado. No se ha modificado el inventario."
            else:
                piezas = {p.pk: p for p in M.objects.select_for_update().filter(pk__in=ids_solicitados).order_by("pk")}
                if len(piezas) != len(ids_solicitados):
                    error = "Una de las piezas ya no existe. Recarga el formulario. No se ha modificado el inventario."
                else:
                    totales = {}
                    for linea in filas:
                        totales[linea["pieza"]] = totales.get(linea["pieza"], 0) + linea["cantidad"]
                    insuficientes = [p for pk, p in piezas.items() if p.restante < totales.get(pk, 0)]
                    if insuficientes:
                        error = "Stock insuficiente: " + "; ".join(
                            f"{p.codigo} — {p.nombre}: hay {p.restante}, hacen falta {totales[p.pk]}"
                            for p in insuficientes
                        ) + ". No se ha descontado ninguna pieza."
                    else:
                        detalles_movimiento = {pk: [] for pk in piezas}
                        for linea in filas:
                            detalles_movimiento[linea["pieza"]].append(linea)
                        for pk in sorted(piezas):
                            p = piezas[pk]
                            anterior = p.restante
                            p.restante -= totales[pk]
                            p.version += 1
                            p.save(update_fields=["restante", "version", "updated_at"])
                            detalle_lineas = ", ".join(
                                f"{linea['cantidad']} {dict(ORIGENES_PIEZA_AVERIA)[linea['origen']].lower()}"
                                for linea in detalles_movimiento[pk]
                            )
                            mov(request, tabla=informe.tabla, codigo=p.codigo, tipo="averia",
                                anterior=anterior, nuevo=p.restante,
                                detalle=f"Informe #{informe.pk}, serie {informe.numero_serie}: {detalle_lineas}")
                        for linea in filas:
                            p = piezas[linea["pieza"]]
                            PiezaInformeAveria.objects.create(
                                informe=informe, pieza_id_inventario=p.pk, pieza_codigo=p.codigo,
                                pieza_nombre=p.nombre, cantidad=linea["cantidad"], origen=linea["origen"]
                            )
                        informe.reparacion_realizada = reparacion
                        informe.estado = "completada"
                        informe.reparado_por = request.user
                        informe.completado_en = timezone.now()
                        informe.save(update_fields=["reparacion_realizada", "estado", "reparado_por",
                                                     "completado_en", "actualizado_en"])

    if error:
        return render(request, "inventario/averia_detalle.html",
                      _contexto_informe_averia(informe, filas, error, reparacion), status=409)
    # CINCOS-AVERIA-CIERRE-REDIRECT-v1
    messages.success(request, f"El informe de avería #{informe_id} se ha cerrado correctamente.")
    return redirect("inicio")


def _filas_formulario(ids_post, cantidades_post, origenes_post):
    filas = []
    for i in range(max(len(ids_post), len(cantidades_post), len(origenes_post))):
        filas.append({
            "pieza": ids_post[i] if i < len(ids_post) else "",
            "cantidad": cantidades_post[i] if i < len(cantidades_post) else "",
            "origen": origenes_post[i] if i < len(origenes_post) else "nueva",
        })
    return filas or [{"pieza": "", "cantidad": "", "origen": "nueva"}]

# CINCOS-INFORMES-GLOBALES-v1
@login_required
def informes(request):
    """Lista global de averías pendientes y reparaciones completadas."""
    pendientes = list(
        InformeAveria.objects.filter(estado="pendiente")
        .select_related("creado_por")
        .order_by("-creado_en", "-pk")
    )
    completados = list(
        InformeAveria.objects.filter(estado="completada")
        .select_related("creado_por", "reparado_por")
        .order_by("-completado_en", "-pk")
    )

    # Añadir nombres visibles y enlace de vuelta al modelo para ambas listas.
    for informe in pendientes + completados:
        cfg = PAGINAS.get(informe.tabla, {})
        informe.nombre_seccion = cfg.get("seccion", informe.get_tabla_display())
        informe.nombre_variante = VARS.get(informe.tabla, {}).get(
            informe.variante, informe.variante.capitalize()
        )
        ruta_var = cfg.get("ruta_var")
        variantes_validas = VARS.get(informe.tabla, {})
        if ruta_var and informe.variante in variantes_validas:
            informe.url_modelo = reverse(ruta_var, args=[informe.variante])
        else:
            informe.url_modelo = reverse("inicio")

    return render(request, "inventario/informes.html", {
        "seccion": "informes",
        "pendientes": pendientes,
        "total_pendientes": len(pendientes),
        "completados": completados,
        "total_completados": len(completados),
    })


