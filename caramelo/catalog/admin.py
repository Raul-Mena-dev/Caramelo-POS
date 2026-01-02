from django.contrib import admin
from .models import GrupoProducto, SubgrupoProducto, Producto


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
    list_display = ("nombre", "precio_con_iva", "stock_actual", "barcode", "grupo", "subgrupo", "activo")
    search_fields = ("nombre", "sku", "barcode", "grupo__nombre", "subgrupo__nombre")
    list_filter = ("activo", "grupo", "subgrupo")
