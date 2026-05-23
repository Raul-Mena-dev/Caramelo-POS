from django.db import models
from django.contrib.auth import get_user_model
from catalog.models import Producto

User = get_user_model()


class ClienteFiscal(models.Model):
    TIPOS_PERSONA = [
        ("FISICA", "Persona fisica"),
        ("MORAL", "Persona moral"),
    ]

    razon_social = models.CharField(max_length=180)
    rfc = models.CharField(max_length=13, unique=True)
    regimen_fiscal = models.CharField(max_length=120, blank=True, default="")
    codigo_postal = models.CharField(max_length=10, blank=True, default="")
    uso_cfdi = models.CharField(max_length=40, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    tipo_persona = models.CharField(max_length=10, choices=TIPOS_PERSONA, default="FISICA")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["razon_social"]

    def __str__(self):
        return f"{self.razon_social} ({self.rfc})"


class Venta(models.Model):
    METODOS = [
        ("EFECTIVO", "Efectivo"),
        ("TARJETA", "Tarjeta"),
        ("TRANSFER", "Transferencia"),
    ]
    folio = models.BigIntegerField(unique=True)
    fecha = models.DateTimeField(auto_now_add=True)
    metodo_pago = models.CharField(max_length=20, choices=METODOS)
    subtotal_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_ieps = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_iva = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    retencion_isr = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estatus = models.CharField(max_length=20, default="ACTIVA")  # fase 2: CANCELADA
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    turno = models.ForeignKey("CajaTurno", on_delete=models.PROTECT, related_name="ventas", null=True, blank=True)
    cliente_fiscal = models.ForeignKey(ClienteFiscal, on_delete=models.PROTECT, null=True, blank=True, related_name="ventas")

    def __str__(self):
        return f"V{self.folio}"

class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="items")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    base_unitaria = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ieps_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_unitario_con_iva = models.DecimalField(max_digits=12, decimal_places=2)
    base_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ieps_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    iva_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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


class VentaSinStock(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name="faltantes_stock")
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad_solicitada = models.DecimalField(max_digits=12, decimal_places=3)
    stock_disponible = models.DecimalField(max_digits=12, decimal_places=3)
    cantidad_faltante = models.DecimalField(max_digits=12, decimal_places=3)
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.producto} faltante {self.cantidad_faltante}"


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
