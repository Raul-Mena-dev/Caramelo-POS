from django.db import models
from django.contrib.auth import get_user_model
from catalog.models import Producto

User = get_user_model()

class Venta(models.Model):
    METODOS = [
        ("EFECTIVO", "Efectivo"),
        ("TARJETA", "Tarjeta"),
        ("TRANSFER", "Transferencia"),
    ]
    folio = models.BigIntegerField(unique=True)
    fecha = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estatus = models.CharField(max_length=20, default="ACTIVA")  # fase 2: CANCELADA
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    turno = models.ForeignKey("CajaTurno", on_delete=models.PROTECT, related_name="ventas", null=True, blank=True)

    def __str__(self):
        return f"V{self.folio}"

class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    precio_unitario_con_iva = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

class MovimientoInventario(models.Model):
    TIPOS = [
        ("ENTRADA", "Entrada"),
        ("AJUSTE", "Ajuste"),
        ("VENTA", "Venta"),
        ("CANCELACION", "Cancelación"),  # fase 2
    ]
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)  # + o -
    referencia = models.CharField(max_length=60, blank=True, default="")
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    

User = get_user_model()

class CajaTurno(models.Model):
    ESTATUS = [
        ("ABIERTO", "Abierto"),
        ("CERRADO", "Cerrado"),
    ]

    caja_nombre = models.CharField(max_length=40, default="CAJA1")  # CAJA1/CAJA2
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    estatus = models.CharField(max_length=10, choices=ESTATUS, default="ABIERTO")

    apertura = models.DateTimeField(auto_now_add=True)
    cierre = models.DateTimeField(blank=True, null=True)

    fondo_inicial = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Al cerrar (fase 1: solo efectivo contado)
    efectivo_contado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Totales “snapshots” opcionales (se pueden recalcular, pero es útil guardarlos)
    total_ventas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_tarjeta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_transfer = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    diferencia_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.caja_nombre} - {self.usuario} - {self.estatus}"

