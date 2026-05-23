from django.urls import path

from . import views

urlpatterns = [
    path("productos/nuevo/", views.producto_alta, name="catalog_producto_alta"),
    path("productos/rapido/", views.producto_rapido, name="catalog_producto_rapido"),
    path("productos/<int:producto_id>/editar/", views.producto_editar, name="catalog_producto_editar"),
    path("productos/<int:producto_id>/borrar/", views.producto_borrar, name="catalog_producto_borrar"),
    path("inventario/", views.inventario, name="catalog_inventario"),
    path("compras/nueva/", views.entrada_compra, name="catalog_entrada_compra"),
    path("inventario/ajuste/", views.ajuste_inventario, name="catalog_ajuste_inventario"),
    path("productos/<int:producto_id>/etiquetas.pdf", views.etiquetas_pdf, name="catalog_etiquetas"),
]
