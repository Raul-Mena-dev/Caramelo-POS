from django import forms

from .models import GrupoProducto, SubgrupoProducto, Producto

DEFAULT_MARGEN = 35
DEFAULT_IEPS = 8
DEFAULT_IVA = 16


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
            "costo_compra",
            "unidades_compra",
            "ieps_porcentaje",
            "iva_porcentaje",
            "margen_porcentaje",
            "precio_sin_impuestos",
            "precio_calculado",
            "precio_mandatorio",
            "usar_precio_mandatorio",
            "stock_actual",
            "stock_minimo",
            "unidad_venta",
            "no_contabilizable",
            "activo",
        ]
        widgets = {
            "precio_sin_impuestos": forms.NumberInput(attrs={"readonly": "readonly"}),
            "precio_calculado": forms.NumberInput(attrs={"readonly": "readonly"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["precio_con_iva"].required = False
        self.fields["precio_sin_impuestos"].required = False
        self.fields["precio_calculado"].required = False
        self.fields["sku"].required = False
        self.fields["costo"].required = False
        self.fields["costo_compra"].required = True
        self.fields["unidades_compra"].required = True
        self.fields["stock_actual"].required = False
        self.fields["stock_minimo"].required = False
        self.fields["ieps_porcentaje"].initial = self.fields["ieps_porcentaje"].initial or DEFAULT_IEPS
        self.fields["iva_porcentaje"].initial = self.fields["iva_porcentaje"].initial or DEFAULT_IVA
        self.fields["margen_porcentaje"].initial = self.fields["margen_porcentaje"].initial or DEFAULT_MARGEN
        for name, field in self.fields.items():
            if name in {"activo", "generar_barcode", "generar_qr", "usar_precio_mandatorio", "no_contabilizable"}:
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        grupo = (cleaned.get("grupo_nombre") or "").strip()
        subgrupo = (cleaned.get("subgrupo_nombre") or "").strip()
        if subgrupo and not grupo:
            self.add_error("grupo_nombre", "Grupo requerido si hay subgrupo.")
        precio_capturado = cleaned.get("precio_con_iva")
        if cleaned.get("usar_precio_mandatorio") and not (cleaned.get("precio_mandatorio") or precio_capturado):
            self.add_error("precio_mandatorio", "Captura el precio mandatorio.")
        if not cleaned.get("usar_precio_mandatorio") and not precio_capturado and (cleaned.get("unidades_compra") or 0) <= 0:
            self.add_error("unidades_compra", "Las unidades deben ser mayores a cero.")
        unidades_compra = cleaned.get("unidades_compra") or 0
        if not cleaned.get("stock_actual"):
            cleaned["stock_actual"] = unidades_compra
        if not cleaned.get("stock_minimo"):
            cleaned["stock_minimo"] = 0
        if not cleaned.get("iva_porcentaje"):
            cleaned["iva_porcentaje"] = DEFAULT_IVA
        if cleaned.get("ieps_porcentaje") is None:
            cleaned["ieps_porcentaje"] = DEFAULT_IEPS
        if not cleaned.get("margen_porcentaje"):
            cleaned["margen_porcentaje"] = DEFAULT_MARGEN
        if precio_capturado:
            cleaned["precio_mandatorio"] = precio_capturado
            cleaned["usar_precio_mandatorio"] = True
        cleaned["grupo_nombre"] = grupo
        cleaned["subgrupo_nombre"] = subgrupo
        return cleaned

    def save(self, commit=True):
        producto = super().save(commit=False)
        producto.calcular_precio()
        if commit:
            producto.save()
            self.save_m2m()
        return producto

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


class EntradaCompraForm(forms.Form):
    producto = forms.ModelChoiceField(queryset=Producto.objects.filter(activo=True).order_by("nombre"))
    cantidad = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, label="Cantidad a sumar")
    costo_compra = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Costo total de compra")
    unidades_compra = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, label="Unidades compradas")
    ieps_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=DEFAULT_IEPS, label="IEPS %")
    iva_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=DEFAULT_IVA, label="IVA %")
    margen_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=0, label="Margen %")
    precio_mandatorio = forms.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0, label="Precio mandatorio")
    usar_precio_mandatorio = forms.BooleanField(required=False, label="Usar precio mandatorio")
    referencia = forms.CharField(max_length=60, required=False, label="Referencia")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == "usar_precio_mandatorio":
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("usar_precio_mandatorio") and not cleaned.get("precio_mandatorio"):
            self.add_error("precio_mandatorio", "Captura el precio mandatorio.")
        return cleaned


class ProductoRapidoForm(forms.ModelForm):
    grupo_nombre = forms.CharField(required=False, label="Grupo")
    costo_compra = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Costo total de compra")
    unidades_compra = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, label="Piezas compradas")
    margen_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=DEFAULT_MARGEN, label="Margen %")

    class Meta:
        model = Producto
        fields = [
            "barcode",
            "nombre",
            "precio_con_iva",
            "costo_compra",
            "unidades_compra",
            "margen_porcentaje",
            "stock_actual",
            "stock_minimo",
            "unidad_venta",
        ]

    def __init__(self, *args, **kwargs):
        barcode = kwargs.pop("barcode", "")
        super().__init__(*args, **kwargs)
        if barcode:
            self.fields["barcode"].initial = barcode
        self.fields["precio_con_iva"].required = False
        self.fields["stock_actual"].required = False
        self.fields["stock_minimo"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        cleaned["grupo_nombre"] = (cleaned.get("grupo_nombre") or "").strip()
        if not cleaned.get("stock_actual"):
            cleaned["stock_actual"] = cleaned.get("unidades_compra") or 0
        if not cleaned.get("stock_minimo"):
            cleaned["stock_minimo"] = 0
        return cleaned

    def save(self, commit=True):
        producto = super().save(commit=False)
        producto.costo_compra = self.cleaned_data["costo_compra"]
        producto.unidades_compra = self.cleaned_data["unidades_compra"]
        producto.margen_porcentaje = self.cleaned_data["margen_porcentaje"]
        producto.stock_actual = self.cleaned_data["stock_actual"]
        producto.stock_minimo = self.cleaned_data["stock_minimo"]
        producto.iva_porcentaje = DEFAULT_IVA
        producto.ieps_porcentaje = DEFAULT_IEPS
        if self.cleaned_data.get("precio_con_iva"):
            producto.precio_mandatorio = self.cleaned_data["precio_con_iva"]
            producto.usar_precio_mandatorio = True
        else:
            producto.usar_precio_mandatorio = False
        producto.calcular_precio()
        producto.activo = True
        if commit:
            grupo_nombre = self.cleaned_data.get("grupo_nombre")
            if grupo_nombre:
                producto.grupo, _ = GrupoProducto.objects.get_or_create(nombre=grupo_nombre)
            producto.save()
        return producto


class AjusteInventarioForm(forms.Form):
    producto = forms.ModelChoiceField(queryset=Producto.objects.filter(activo=True).order_by("nombre"))
    cantidad = forms.DecimalField(max_digits=12, decimal_places=3, label="Cantidad")
    motivo = forms.CharField(max_length=60, required=False, label="Motivo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
