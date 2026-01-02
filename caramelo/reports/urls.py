from django.urls import path
from . import views

urlpatterns = [
    path("diario/", views.corte_diario, name="corte_diario"),   # lo vamos a reutilizar como "por rango"
    path("diario.pdf", views.corte_diario_pdf, name="corte_diario_pdf"),
    path("turno/<int:turno_id>/", views.corte_turno, name="corte_turno"),
    path("turno/<int:turno_id>.pdf", views.corte_turno_pdf, name="corte_turno_pdf"),
]
