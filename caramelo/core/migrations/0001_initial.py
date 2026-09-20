from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ConfiguracionNegocio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre_comercial", models.CharField(default="Mi Negocio", max_length=120)),
                ("razon_social", models.CharField(blank=True, default="", max_length=180)),
                ("rfc", models.CharField(blank=True, default="", max_length=13)),
                ("domicilio", models.CharField(blank=True, default="", max_length=240)),
                ("telefono", models.CharField(blank=True, default="", max_length=30)),
                ("logo_url", models.URLField(blank=True, default="")),
                ("color_primario", models.CharField(default="#2563eb", max_length=7)),
                ("color_secundario", models.CharField(default="#1e3a8a", max_length=7)),
                ("mensaje_ticket", models.CharField(default="Gracias por su compra", max_length=180)),
                ("moneda", models.CharField(default="MXN", max_length=3)),
                ("iva_predeterminado", models.DecimalField(decimal_places=2, default=0, max_digits=5, validators=[MinValueValidator(Decimal("0"))])),
                ("ieps_predeterminado", models.DecimalField(decimal_places=2, default=0, max_digits=5, validators=[MinValueValidator(Decimal("0"))])),
                ("margen_predeterminado", models.DecimalField(decimal_places=2, default=30, max_digits=5, validators=[MinValueValidator(Decimal("0"))])),
                ("redondeo_precios", models.CharField(choices=[("0.01", "Sin redondeo adicional"), ("0.10", "Al siguiente $0.10"), ("0.50", "Al siguiente $0.50"), ("1.00", "Al siguiente $1.00")], default="0.01", max_length=4)),
                ("permitir_venta_sin_stock", models.BooleanField(default=False)),
                ("aplicar_retencion_persona_moral", models.BooleanField(default=False)),
                ("retencion_persona_moral", models.DecimalField(decimal_places=4, default=Decimal("1.2500"), max_digits=6, validators=[MinValueValidator(Decimal("0"))])),
            ],
            options={"verbose_name": "configuracion del negocio", "verbose_name_plural": "configuracion del negocio"},
        ),
    ]
