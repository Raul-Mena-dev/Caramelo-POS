from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0005_alter_producto_ieps_porcentaje")]

    operations = [
        migrations.AddField(model_name="producto", name="marca", field=models.CharField(blank=True, default="", max_length=100)),
        migrations.AddField(model_name="producto", name="presentacion_compra", field=models.CharField(blank=True, default="Pieza", max_length=40)),
        migrations.AddField(model_name="producto", name="factor_conversion_compra", field=models.DecimalField(decimal_places=3, default=1, max_digits=12)),
        migrations.AddField(model_name="producto", name="controla_inventario", field=models.BooleanField(default=True)),
        migrations.AlterField(model_name="producto", name="ieps_porcentaje", field=models.DecimalField(decimal_places=2, default=0, max_digits=5)),
        migrations.AlterField(model_name="producto", name="iva_porcentaje", field=models.DecimalField(decimal_places=2, default=0, max_digits=5)),
        migrations.AlterField(
            model_name="producto",
            name="unidad_venta",
            field=models.CharField(
                choices=[("PIEZA", "Pieza"), ("KG", "Kilogramo"), ("GR", "Gramo"), ("L", "Litro"), ("ML", "Mililitro"), ("PAQUETE", "Paquete"), ("CAJA", "Caja"), ("SERVICIO", "Servicio")],
                default="PIEZA",
                max_length=10,
            ),
        ),
    ]
