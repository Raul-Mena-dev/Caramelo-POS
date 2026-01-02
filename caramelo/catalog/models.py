from django.db import models


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
    nombre = models.CharField(max_length=180)
    sku = models.CharField(max_length=60, blank=True, default="")
    barcode = models.CharField(max_length=80, blank=True, null=True, unique=True)
    precio_con_iva = models.DecimalField(max_digits=12, decimal_places=2)
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_actual = models.DecimalField(max_digits=12, decimal_places=3, default=0)  # permite 0.500 etc
    activo = models.BooleanField(default=True)
    grupo = models.ForeignKey(GrupoProducto, on_delete=models.PROTECT, null=True, blank=True, related_name="productos")
    subgrupo = models.ForeignKey(SubgrupoProducto, on_delete=models.PROTECT, null=True, blank=True, related_name="productos")

    def __str__(self):
        return self.nombre
