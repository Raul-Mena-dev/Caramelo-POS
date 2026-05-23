from decimal import Decimal, ROUND_CEILING

from django.db import models


MONEY = Decimal("0.01")
HALF_PESO = Decimal("0.50")


def _money(value):
    return Decimal(value or "0").quantize(MONEY)


def redondear_medio_peso_arriba(value):
    value = Decimal(value or "0")
    if value <= 0:
        return Decimal("0.00")
    units = (value / HALF_PESO).to_integral_value(rounding=ROUND_CEILING)
    return (units * HALF_PESO).quantize(MONEY)


class GrupoProducto(models.Model):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class SubgrupoProducto(models.Model):
    grupo = models.ForeignKey(GrupoProducto, on_delete=models.PROTECT, related_name="subgrupos")
    nombre = models.CharField(max_length=80)

    class Meta:
        ordering = ["grupo__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["grupo", "nombre"], name="uniq_subgrupo_por_grupo"),
        ]

    def __str__(self):
        return f"{self.grupo.nombre} / {self.nombre}"


class Producto(models.Model):
    UNIDADES_VENTA = [
        ("PIEZA", "Pieza"),
        ("KG", "Kilogramo"),
    ]

    nombre = models.CharField(max_length=180)
    sku = models.CharField(max_length=60, blank=True, default="")
    barcode = models.CharField(max_length=80, blank=True, null=True, unique=True)
    precio_con_iva = models.DecimalField(max_digits=12, decimal_places=2)
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costo_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unidades_compra = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    ieps_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=8)
    iva_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=16)
    margen_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    precio_sin_impuestos = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_calculado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    precio_mandatorio = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    usar_precio_mandatorio = models.BooleanField(default=False)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=3, default=0)  # permite 0.500 etc
    stock_minimo = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    unidad_venta = models.CharField(max_length=10, choices=UNIDADES_VENTA, default="PIEZA")
    no_contabilizable = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    grupo = models.ForeignKey(GrupoProducto, on_delete=models.PROTECT, null=True, blank=True, related_name="productos")
    subgrupo = models.ForeignKey(SubgrupoProducto, on_delete=models.PROTECT, null=True, blank=True, related_name="productos")

    def calcular_precio(self):
        unidades = Decimal(self.unidades_compra or "0")
        costo_compra = Decimal(self.costo_compra or self.costo or "0")
        if unidades <= 0:
            unidades = Decimal("1")

        costo_unitario = costo_compra / unidades
        margen = Decimal("1") + (Decimal(self.margen_porcentaje or "0") / Decimal("100"))
        ieps_tasa = Decimal(self.ieps_porcentaje or "0") / Decimal("100")
        iva_tasa = Decimal(self.iva_porcentaje or "0") / Decimal("100")

        precio_sin_impuestos = costo_unitario * margen
        ieps = precio_sin_impuestos * ieps_tasa
        iva = (precio_sin_impuestos + ieps) * iva_tasa
        precio_calculado = precio_sin_impuestos + ieps + iva

        self.precio_sin_impuestos = _money(precio_sin_impuestos)
        self.precio_calculado = _money(precio_calculado)
        if self.usar_precio_mandatorio and self.precio_mandatorio:
            self.precio_con_iva = _money(self.precio_mandatorio)
        else:
            self.precio_con_iva = redondear_medio_peso_arriba(precio_calculado)
        self.costo = _money(costo_unitario)
        return self.precio_con_iva

    def desglose_unitario(self):
        precio_final = Decimal(self.precio_con_iva or "0")
        ieps_tasa = Decimal(self.ieps_porcentaje or "0") / Decimal("100")
        iva_tasa = Decimal(self.iva_porcentaje or "0") / Decimal("100")
        factor = (Decimal("1") + ieps_tasa) * (Decimal("1") + iva_tasa)
        if factor <= 0:
            factor = Decimal("1")
        base = precio_final / factor
        ieps = base * ieps_tasa
        iva = (base + ieps) * iva_tasa
        return {
            "base": _money(base),
            "ieps": _money(ieps),
            "iva": _money(iva),
            "precio": _money(precio_final),
        }

    def __str__(self):
        return self.nombre
