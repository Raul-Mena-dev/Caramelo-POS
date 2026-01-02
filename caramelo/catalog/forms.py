from django import forms

from .models import GrupoProducto, SubgrupoProducto, Producto


class ProductoAltaForm(forms.ModelForm):
    grupo_nombre = forms.CharField(required=False, label="Grupo")
    subgrupo_nombre = forms.CharField(required=False, label="Subgrupo")
    generar_barcode = forms.BooleanField(required=False, initial=True, label="Generar codigo de barras")
    generar_qr = forms.BooleanField(required=False, initial=True, label="Generar QR")
    etiquetas_qty = forms.IntegerField(required=False, min_value=1, initial=1, label="Cantidad de etiquetas")

    class Meta:
        model = Producto
        fields = [
            "nombre",
            "sku",
            "barcode",
            "precio_con_iva",
            "costo",
            "stock_actual",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in {"activo", "generar_barcode", "generar_qr"}:
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        grupo = (cleaned.get("grupo_nombre") or "").strip()
        subgrupo = (cleaned.get("subgrupo_nombre") or "").strip()
        if subgrupo and not grupo:
            self.add_error("grupo_nombre", "Grupo requerido si hay subgrupo.")
        cleaned["grupo_nombre"] = grupo
        cleaned["subgrupo_nombre"] = subgrupo
        return cleaned

    def get_or_create_grupos(self):
        grupo = None
        subgrupo = None
        grupo_nombre = self.cleaned_data.get("grupo_nombre")
        subgrupo_nombre = self.cleaned_data.get("subgrupo_nombre")

        if grupo_nombre:
            grupo, _ = GrupoProducto.objects.get_or_create(nombre=grupo_nombre)
        if subgrupo_nombre and grupo:
            subgrupo, _ = SubgrupoProducto.objects.get_or_create(
                grupo=grupo,
                nombre=subgrupo_nombre,
            )
        return grupo, subgrupo
