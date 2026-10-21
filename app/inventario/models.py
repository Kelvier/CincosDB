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

    class Meta:
        ordering = ["-fecha"]
