from django.urls import path

from . import views

urlpatterns = [
    path("productos/nuevo/", views.producto_alta, name="catalog_producto_alta"),
    path("productos/<int:producto_id>/editar/", views.producto_editar, name="catalog_producto_editar"),
    path("inventario/", views.inventario, name="catalog_inventario"),
    path("productos/<int:producto_id>/etiquetas.pdf", views.etiquetas_pdf, name="catalog_etiquetas"),
]
