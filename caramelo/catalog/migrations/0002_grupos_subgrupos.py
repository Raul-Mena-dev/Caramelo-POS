from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrupoProducto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80, unique=True)),
            ],
            options={
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="SubgrupoProducto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80)),
                ("grupo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="subgrupos", to="catalog.grupoproducto")),
            ],
            options={
                "ordering": ["grupo__nombre", "nombre"],
            },
        ),
        migrations.AddConstraint(
            model_name="subgrupoproducto",
            constraint=models.UniqueConstraint(fields=("grupo", "nombre"), name="uniq_subgrupo_por_grupo"),
        ),
        migrations.AddField(
            model_name="producto",
            name="grupo",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="productos", to="catalog.grupoproducto"),
        ),
        migrations.AddField(
            model_name="producto",
            name="subgrupo",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="productos", to="catalog.subgrupoproducto"),
        ),
    ]
