from django.contrib import admin
from .models import Venta, VentaItem, MovimientoInventario

class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 0

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("folio", "fecha", "metodo_pago", "total", "estatus", "usuario")
    inlines = [VentaItemInline]

@admin.register(MovimientoInventario)
class MovAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "producto", "cantidad", "referencia", "usuario")
