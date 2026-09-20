from django.contrib import admin
from .models import Compra, CompraItem, GrupoProducto, Proveedor, SubgrupoProducto, Producto


@admin.register(GrupoProducto)
class GrupoProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre",)
    search_fields = ("nombre",)


@admin.register(SubgrupoProducto)
class SubgrupoProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "grupo")
    search_fields = ("nombre", "grupo__nombre")
    list_filter = ("grupo",)

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "marca", "precio_con_iva", "unidad_venta", "stock_actual", "stock_minimo", "barcode", "grupo", "controla_inventario", "activo")
    search_fields = ("nombre", "marca", "sku", "barcode", "grupo__nombre", "subgrupo__nombre")
    list_filter = ("activo", "unidad_venta", "controla_inventario", "no_contabilizable", "grupo", "subgrupo")


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rfc", "contacto", "telefono", "activo")
    search_fields = ("nombre", "rfc", "contacto")
    list_filter = ("activo",)


class CompraItemInline(admin.TabularInline):
    model = CompraItem
    extra = 0
    readonly_fields = ("producto", "cantidad_presentaciones", "factor_conversion", "cantidad_unidades", "costo_total", "costo_unitario", "costo_promedio_resultante", "stock_anterior", "stock_nuevo")


@admin.register(Compra)
class CompraAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha", "proveedor", "documento", "total", "estatus", "usuario")
    list_filter = ("estatus", "proveedor")
    search_fields = ("documento", "proveedor__nombre")
    inlines = [CompraItemInline]
