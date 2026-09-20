from django.urls import path
from . import views

urlpatterns = [
    path("", views.pos_home, name="pos_home"),
    path("add/", views.pos_add_item, name="pos_add_item"),
    path("clear/", views.pos_clear_cart, name="pos_clear_cart"),
    path("checkout/", views.pos_checkout, name="pos_checkout"),
    path("ticket/<int:venta_id>.pdf", views.ticket_pdf, name="ticket_pdf"),
    path("venta/<int:venta_id>/cancelar/", views.venta_cancelar, name="venta_cancelar"),
    path("turno/", views.turno_home, name="turno_home"),
    path("turno/abrir/", views.turno_abrir, name="turno_abrir"),
    path("turno/cerrar/", views.turno_cerrar, name="turno_cerrar"),
]
