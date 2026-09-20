from django.urls import path
from . import views

urlpatterns = [
    path("diario/", views.corte_diario, name="corte_diario"),   # lo vamos a reutilizar como "por rango"
    path("diario.pdf", views.corte_diario_pdf, name="corte_diario_pdf"),
    path("diario.csv", views.corte_diario_csv, name="corte_diario_csv"),
    path("sin-stock/", views.ventas_sin_stock, name="ventas_sin_stock"),
    path("sin-stock.csv", views.ventas_sin_stock_csv, name="ventas_sin_stock_csv"),
    path("inventario/", views.inventario_valorizado, name="inventario_valorizado"),
    path("inventario.csv", views.inventario_valorizado_csv, name="inventario_valorizado_csv"),
    path("turno/<int:turno_id>/", views.corte_turno, name="corte_turno"),
    path("turno/<int:turno_id>.pdf", views.corte_turno_pdf, name="corte_turno_pdf"),
]
