from django.contrib import admin
from .models import CajaTurno, ClienteFiscal, Venta, VentaItem, MovimientoInventario, VentaSinStock


@admin.register(ClienteFiscal)
class ClienteFiscalAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "rfc", "tipo_persona", "email", "activo")
    search_fields = ("razon_social", "rfc", "email")
    list_filter = ("tipo_persona", "activo")

class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 0

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ("folio", "fecha", "metodo_pago", "subtotal_base", "total_ieps", "total_iva", "retencion_isr", "total", "estatus", "usuario")
    list_filter = ("metodo_pago", "estatus")
    inlines = [VentaItemInline]

@admin.register(MovimientoInventario)
class MovAdmin(admin.ModelAdmin):
    list_display = ("fecha", "tipo", "producto", "cantidad", "referencia", "usuario")


@admin.register(CajaTurno)
class CajaTurnoAdmin(admin.ModelAdmin):
    list_display = ("caja_nombre", "usuario", "estatus", "apertura", "cierre", "total_ventas")
    list_filter = ("estatus", "caja_nombre")


@admin.register(VentaSinStock)
class VentaSinStockAdmin(admin.ModelAdmin):
    list_display = ("fecha", "venta", "producto", "cantidad_solicitada", "stock_disponible", "cantidad_faltante", "usuario")
    search_fields = ("producto__nombre", "venta__folio", "usuario__username")
