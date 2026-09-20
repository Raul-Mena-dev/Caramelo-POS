from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def inicializar_folio(apps, schema_editor):
    Venta = apps.get_model("sales", "Venta")
    FolioVenta = apps.get_model("sales", "FolioVenta")
    ultimo = Venta.objects.order_by("-folio").values_list("folio", flat=True).first() or 0
    FolioVenta.objects.update_or_create(pk=1, defaults={"ultimo": ultimo})


class Migration(migrations.Migration):
    dependencies = [("sales", "0004_ventasinstock")]

    operations = [
        migrations.CreateModel(
            name="FolioVenta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ultimo", models.BigIntegerField(default=0)),
            ],
        ),
        migrations.AddField(model_name="venta", name="efectivo_recibido", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name="venta", name="cambio", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.AddField(model_name="venta", name="cancelada_en", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="venta", name="motivo_cancelacion", field=models.CharField(blank=True, default="", max_length=180)),
        migrations.AddField(model_name="venta", name="cancelada_por", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ventas_canceladas", to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="venta", name="estatus", field=models.CharField(choices=[("ACTIVA", "Activa"), ("CANCELADA", "Cancelada")], default="ACTIVA", max_length=20)),
        migrations.AddField(model_name="ventaitem", name="costo_unitario", field=models.DecimalField(decimal_places=2, default=0, max_digits=12)),
        migrations.RunPython(inicializar_folio, migrations.RunPython.noop),
    ]
