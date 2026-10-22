from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

QUIEN = [("ANIMA", "ANIMA"), ("CERC", "CERC"), ("CINCOS", "CINCOS")]


class PiezaBase(models.Model):
    CAMPO_RAPIDO = "restante"
    codigo = models.CharField("Código", max_length=30, unique=True)
    nombre = models.CharField("Nombre", max_length=200)
    inicial = models.IntegerField("Inicial", default=0)
    por_unidad = models.PositiveIntegerField("x Unidad", default=1)
    restante = models.IntegerField("Restante", default=0)
    ideal = models.PositiveIntegerField("Ideal", default=0)
    quien = models.CharField("Quién", max_length=10, choices=QUIEN)
    version = models.PositiveIntegerField(default=1)  # bloqueo optimista
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["codigo"]

    @property
    def bajo(self):
        return self.restante < self.ideal

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class PiezaOcarina(PiezaBase):
    por_unidad = models.PositiveIntegerField("x Máquina", default=1)
    COLUMNAS = ["codigo", "nombre", "inicial", "por_unidad", "restante", "estado", "ideal", "quien"]
    CAMPOS_FORM = ["codigo", "nombre", "inicial", "por_unidad", "restante", "ideal", "quien"]

    class Meta(PiezaBase.Meta):
        verbose_name = "pieza de ocarina"


class PiezaManipulo(PiezaBase):
    por_unidad = models.PositiveIntegerField("x Manípulo", default=1)
    reutilizables = models.BooleanField("Reutilizable", default=False)
    reciclados = models.PositiveIntegerField("Reciclados", default=0)
    COLUMNAS = ["codigo", "nombre", "inicial", "por_unidad", "restante", "estado", "ideal",
                "reutilizables", "reciclados", "quien"]
    CAMPOS_FORM = ["codigo", "nombre", "inicial", "por_unidad", "restante", "ideal",
                   "reutilizables", "reciclados", "quien"]

    class Meta(PiezaBase.Meta):
        verbose_name = "pieza de manípulo"


class Contador(models.Model):
    """Números de las cabeceras (enviados, terminados, devueltos...)."""
    CAMPO_RAPIDO = "valor"
    CAMPOS_FORM = ["valor"]
    GRUPOS = [("ocarina", "Ocarinas"), ("manipulo", "Manípulos")]
    grupo = models.CharField(max_length=10, choices=GRUPOS)
    clave = models.SlugField(unique=True)
    etiqueta = models.CharField(max_length=100)
    valor = models.IntegerField("Valor", default=0, validators=[MinValueValidator(0)])
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    bajo = False

    def __str__(self):
        return self.etiqueta


class Movimiento(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    tabla = models.CharField(max_length=10)
    codigo = models.CharField(max_length=60)
    tipo = models.CharField(max_length=10)  # rapida / avanzada / alta / baja
    anterior = models.IntegerField(null=True, blank=True)
    nuevo = models.IntegerField(null=True, blank=True)
    detalle = models.TextField(blank=True)
    lote = models.UUIDField(null=True, blank=True, db_index=True)
    revertido = models.BooleanField(default=False)

    class Meta:
        ordering = ["-fecha"]


VARIANTES = [("nacional", "Nacional"), ("internacional", "Internacional"), ("facial", "Facial")]


class Uso(models.Model):
    """Que piezas lleva cada tipo de manipulo y cuantas por unidad."""
    pieza = models.ForeignKey(PiezaManipulo, on_delete=models.CASCADE, related_name="usos")
    variante = models.CharField(max_length=15, choices=VARIANTES)
    cantidad = models.PositiveIntegerField("x Manipulo", default=1)

    class Meta:
        unique_together = [("pieza", "variante")]
        verbose_name = "pieza por variante"
        verbose_name_plural = "piezas por variante"


OC_VARIANTES = [("nacional", "Nacional"), ("internacional", "Internacional")]


class UsoOcarina(models.Model):
    """Que piezas lleva cada tipo de ocarine y cuantas por maquina."""
    pieza = models.ForeignKey(PiezaOcarina, on_delete=models.CASCADE, related_name="usos")
    variante = models.CharField(max_length=15, choices=OC_VARIANTES)
    cantidad = models.PositiveIntegerField("x Máquina", default=1)

    class Meta:
        unique_together = [("pieza", "variante")]
        verbose_name = "pieza por variante de ocarine"
        verbose_name_plural = "piezas por variante de ocarine"

# ---------- Informes de avería ----------
ESTADOS_INFORME_AVERIA = [
    ("pendiente", "Pendiente de reparación"),
    ("completada", "Reparación completada"),
]
ORIGENES_PIEZA_AVERIA = [
    ("nueva", "Nueva"),
    ("reciclada", "Reciclada"),
]


class InformeAveria(models.Model):
    """Informe iniciado por un usuario y completado por quien realiza la reparación."""
    TABLAS = [("ocarina", "Ocarine"), ("manipulo", "Manípulo")]

    tabla = models.CharField("Equipo", max_length=10, choices=TABLAS)
    variante = models.CharField("Modelo", max_length=15)
    numero_serie = models.CharField("Número de serie", max_length=100)
    descripcion_averia = models.TextField("Descripción de la avería")
    reparacion_realizada = models.TextField("Reparación realizada", blank=True)
    estado = models.CharField("Estado", max_length=12, choices=ESTADOS_INFORME_AVERIA, default="pendiente")
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                  related_name="averias_creadas")
    reparado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="averias_reparadas")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    completado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "informe de avería"
        verbose_name_plural = "informes de avería"

    def __str__(self):
        return f"Avería #{self.pk} · {self.numero_serie} · {self.get_estado_display()}"


class PiezaInformeAveria(models.Model):
    """Instantánea de la pieza utilizada; se conserva aunque después se elimine del catálogo."""
    informe = models.ForeignKey(InformeAveria, on_delete=models.CASCADE, related_name="piezas")
    pieza_id_inventario = models.PositiveIntegerField(null=True, blank=True)
    pieza_codigo = models.CharField("Código de pieza", max_length=30)
    pieza_nombre = models.CharField("Nombre de pieza", max_length=200)
    cantidad = models.PositiveIntegerField("Cantidad")
    origen = models.CharField("Origen", max_length=10, choices=ORIGENES_PIEZA_AVERIA)

    class Meta:
        ordering = ["pieza_codigo", "origen"]
        verbose_name = "pieza de informe de avería"
        verbose_name_plural = "piezas de informes de avería"

    def __str__(self):
        return f"{self.pieza_codigo} × {self.cantidad} ({self.get_origen_display()})"

