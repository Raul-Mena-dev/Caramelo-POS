from django.db import migrations


def estimar_costos(apps, schema_editor):
    VentaItem = apps.get_model("sales", "VentaItem")
    pendientes = list(VentaItem.objects.filter(costo_unitario=0).select_related("producto"))
    actualizados = []
    for item in pendientes:
        costo_actual = item.producto.costo or 0
        if costo_actual > 0:
            item.costo_unitario = costo_actual
            actualizados.append(item)
    if actualizados:
        VentaItem.objects.bulk_update(actualizados, ["costo_unitario"])


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0006_producto_generico"),
        ("sales", "0005_venta_operacion_segura"),
    ]

    operations = [migrations.RunPython(estimar_costos, migrations.RunPython.noop)]
