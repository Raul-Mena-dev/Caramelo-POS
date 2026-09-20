from django.urls import path

from . import views

urlpatterns = [
    path("productos/nuevo/", views.producto_alta, name="catalog_producto_alta"),
    path("productos/rapido/", views.producto_rapido, name="catalog_producto_rapido"),
    path("productos/<int:producto_id>/editar/", views.producto_editar, name="catalog_producto_editar"),
    path("productos/<int:producto_id>/borrar/", views.producto_borrar, name="catalog_producto_borrar"),
    path("inventario/", views.inventario, name="catalog_inventario"),
    path("compras/", views.compras, name="catalog_compras"),
    path("compras/nueva/", views.compra_nueva, name="catalog_compra_nueva"),
    path("compras/<int:compra_id>/", views.compra_detalle, name="catalog_compra_detalle"),
    path("compras/entrada-simple/", views.entrada_compra, name="catalog_entrada_compra"),
    path("proveedores/", views.proveedores, name="catalog_proveedores"),
    path("proveedores/nuevo/", views.proveedor_nuevo, name="catalog_proveedor_nuevo"),
    path("proveedores/<int:proveedor_id>/editar/", views.proveedor_editar, name="catalog_proveedor_editar"),
    path("inventario/ajuste/", views.ajuste_inventario, name="catalog_ajuste_inventario"),
    path("productos/<int:producto_id>/etiquetas.pdf", views.etiquetas_pdf, name="catalog_etiquetas"),
]
