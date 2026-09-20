from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0007_proveedor_compra_compraitem")]

    operations = [
        migrations.AddField(
            model_name="compraitem",
            name="costo_promedio_resultante",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
