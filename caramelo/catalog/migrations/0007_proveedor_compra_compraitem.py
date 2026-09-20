from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_producto_generico"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Proveedor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=180, unique=True)),
                ("rfc", models.CharField(blank=True, default="", max_length=13)),
                ("contacto", models.CharField(blank=True, default="", max_length=120)),
                ("telefono", models.CharField(blank=True, default="", max_length=30)),
                ("email", models.EmailField(blank=True, default="", max_length=254)),
                ("direccion", models.CharField(blank=True, default="", max_length=240)),
                ("notas", models.TextField(blank=True, default="")),
                ("activo", models.BooleanField(default=True)),
            ],
            options={"ordering": ["nombre"]},
        ),
        migrations.CreateModel(
            name="Compra",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("documento", models.CharField(blank=True, default="", max_length=80)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("notas", models.CharField(blank=True, default="", max_length=240)),
                ("estatus", models.CharField(choices=[("RECIBIDA", "Recibida"), ("CANCELADA", "Cancelada")], default="RECIBIDA", max_length=12)),
                ("proveedor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="compras", to="catalog.proveedor")),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-fecha", "-id"]},
        ),
        migrations.CreateModel(
            name="CompraItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cantidad_presentaciones", models.DecimalField(decimal_places=3, max_digits=12, validators=[MinValueValidator(Decimal("0.001"))])),
                ("factor_conversion", models.DecimalField(decimal_places=3, default=1, max_digits=12, validators=[MinValueValidator(Decimal("0.001"))])),
                ("cantidad_unidades", models.DecimalField(decimal_places=3, max_digits=12)),
                ("costo_total", models.DecimalField(decimal_places=2, max_digits=14, validators=[MinValueValidator(Decimal("0"))])),
                ("costo_unitario", models.DecimalField(decimal_places=2, max_digits=12)),
                ("stock_anterior", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("stock_nuevo", models.DecimalField(decimal_places=3, default=0, max_digits=12)),
                ("compra", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="catalog.compra")),
                ("producto", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="compras_items", to="catalog.producto")),
            ],
            options={"ordering": ["id"]},
        ),
    ]
