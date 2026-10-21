from django.contrib import admin
from .models import Movimiento, Uso, UsoOcarina


@admin.register(Movimiento)
class MovimientoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "tabla", "codigo", "tipo", "anterior", "nuevo", "detalle")
    list_filter = ("tabla", "tipo", "usuario")
    search_fields = ("codigo", "detalle")

    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class UsoBase(admin.ModelAdmin):
    list_display = ("variante", "pieza", "cantidad")
    list_editable = ("cantidad",)
    list_filter = ("variante",)
    search_fields = ("pieza__codigo", "pieza__nombre")
    ordering = ("variante", "pieza__codigo")


admin.site.register(Uso, UsoBase)
admin.site.register(UsoOcarina, UsoBase)
