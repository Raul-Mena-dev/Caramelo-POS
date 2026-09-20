from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.utils import OperationalError, ProgrammingError


class ConfiguracionNegocio(models.Model):
    REDONDEOS = [
        ("0.01", "Sin redondeo adicional"),
        ("0.10", "Al siguiente $0.10"),
        ("0.50", "Al siguiente $0.50"),
        ("1.00", "Al siguiente $1.00"),
    ]

    nombre_comercial = models.CharField(max_length=120, default="Mi Negocio")
    razon_social = models.CharField(max_length=180, blank=True, default="")
    rfc = models.CharField(max_length=13, blank=True, default="")
    domicilio = models.CharField(max_length=240, blank=True, default="")
    telefono = models.CharField(max_length=30, blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    color_primario = models.CharField(max_length=7, default="#2563eb")
    color_secundario = models.CharField(max_length=7, default="#1e3a8a")
    mensaje_ticket = models.CharField(max_length=180, default="Gracias por su compra")
    moneda = models.CharField(max_length=3, default="MXN")
    iva_predeterminado = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))]
    )
    ieps_predeterminado = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))]
    )
    margen_predeterminado = models.DecimalField(
        max_digits=5, decimal_places=2, default=30, validators=[MinValueValidator(Decimal("0"))]
    )
    redondeo_precios = models.CharField(max_length=4, choices=REDONDEOS, default="0.01")
    permitir_venta_sin_stock = models.BooleanField(default=False)
    aplicar_retencion_persona_moral = models.BooleanField(default=False)
    retencion_persona_moral = models.DecimalField(
        max_digits=6, decimal_places=4, default=Decimal("1.2500"), validators=[MinValueValidator(Decimal("0"))]
    )

    class Meta:
        verbose_name = "configuracion del negocio"
        verbose_name_plural = "configuracion del negocio"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def cargar(cls):
        try:
            configuracion, _ = cls.objects.get_or_create(pk=1)
            return configuracion
        except (OperationalError, ProgrammingError):
            # Permite ejecutar migraciones y checks antes de crear esta tabla.
            return cls(pk=1)

    def __str__(self):
        return self.nombre_comercial
