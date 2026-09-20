from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from core.models import ConfiguracionNegocio

from .models import Compra, CompraItem, GrupoProducto, Proveedor, SubgrupoProducto, Producto

DEFAULT_MARGEN = 30
DEFAULT_IEPS = 0
DEFAULT_IVA = 0


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
            "marca",
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
            "presentacion_compra",
            "factor_conversion_compra",
            "controla_inventario",
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
        config = ConfiguracionNegocio.cargar()
        self.fields["ieps_porcentaje"].initial = config.ieps_predeterminado
        self.fields["iva_porcentaje"].initial = config.iva_predeterminado
        self.fields["margen_porcentaje"].initial = config.margen_predeterminado
        for name, field in self.fields.items():
            if name in {"activo", "generar_barcode", "generar_qr", "usar_precio_mandatorio", "no_contabilizable", "controla_inventario"}:
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
        if cleaned.get("stock_actual") is None:
            cleaned["stock_actual"] = unidades_compra
        if cleaned.get("stock_minimo") is None:
            cleaned["stock_minimo"] = 0
        if cleaned.get("iva_porcentaje") is None:
            cleaned["iva_porcentaje"] = ConfiguracionNegocio.cargar().iva_predeterminado
        if cleaned.get("ieps_porcentaje") is None:
            cleaned["ieps_porcentaje"] = ConfiguracionNegocio.cargar().ieps_predeterminado
        if cleaned.get("margen_porcentaje") is None:
            cleaned["margen_porcentaje"] = ConfiguracionNegocio.cargar().margen_predeterminado
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
    cantidad = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, required=False, label="Unidades a sumar")
    cantidad_presentaciones = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, required=False, label="Presentaciones compradas")
    factor_conversion = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, required=False, label="Unidades por presentacion")
    costo_compra = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Costo total de compra")
    unidades_compra = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, required=False, label="Unidades para calcular costo")
    ieps_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=DEFAULT_IEPS, label="IEPS %")
    iva_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=DEFAULT_IVA, label="IVA %")
    margen_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=0, label="Margen %")
    precio_mandatorio = forms.DecimalField(max_digits=12, decimal_places=2, required=False, min_value=0, label="Precio mandatorio")
    usar_precio_mandatorio = forms.BooleanField(required=False, label="Usar precio mandatorio")
    referencia = forms.CharField(max_length=60, required=False, label="Referencia")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = ConfiguracionNegocio.cargar()
        self.fields["ieps_porcentaje"].initial = config.ieps_predeterminado
        self.fields["iva_porcentaje"].initial = config.iva_predeterminado
        self.fields["margen_porcentaje"].initial = config.margen_predeterminado
        for name, field in self.fields.items():
            if name == "usar_precio_mandatorio":
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        presentaciones = cleaned.get("cantidad_presentaciones")
        factor = cleaned.get("factor_conversion")
        if presentaciones is not None:
            producto = cleaned.get("producto")
            factor = factor or (producto.factor_conversion_compra if producto else 1) or 1
            cleaned["factor_conversion"] = factor
            cleaned["cantidad"] = presentaciones * factor
        elif cleaned.get("cantidad") is None:
            self.add_error("cantidad", "Captura las unidades a sumar o las presentaciones compradas.")
        if cleaned.get("unidades_compra") is None and cleaned.get("cantidad") is not None:
            cleaned["unidades_compra"] = cleaned["cantidad"]
        if cleaned.get("usar_precio_mandatorio") and not cleaned.get("precio_mandatorio"):
            self.add_error("precio_mandatorio", "Captura el precio mandatorio.")
        return cleaned


class ProductoRapidoForm(forms.ModelForm):
    grupo_nombre = forms.CharField(required=False, label="Grupo")
    costo_compra = forms.DecimalField(max_digits=12, decimal_places=2, min_value=0, label="Costo total de compra")
    unidades_compra = forms.DecimalField(max_digits=12, decimal_places=3, min_value=0.001, label="Unidades compradas")
    margen_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, initial=DEFAULT_MARGEN, label="Margen %")
    ieps_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, required=False, label="IEPS %")
    iva_porcentaje = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, required=False, label="IVA %")

    class Meta:
        model = Producto
        fields = [
            "barcode",
            "nombre",
            "marca",
            "precio_con_iva",
            "costo_compra",
            "unidades_compra",
            "margen_porcentaje",
            "stock_actual",
            "stock_minimo",
            "unidad_venta",
            "ieps_porcentaje",
            "iva_porcentaje",
        ]

    def __init__(self, *args, **kwargs):
        barcode = kwargs.pop("barcode", "")
        super().__init__(*args, **kwargs)
        if barcode:
            self.fields["barcode"].initial = barcode
        config = ConfiguracionNegocio.cargar()
        self.fields["margen_porcentaje"].initial = config.margen_predeterminado
        self.fields["ieps_porcentaje"].initial = config.ieps_predeterminado
        self.fields["iva_porcentaje"].initial = config.iva_predeterminado
        self.fields["precio_con_iva"].required = False
        self.fields["stock_actual"].required = False
        self.fields["stock_minimo"].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        config = ConfiguracionNegocio.cargar()
        cleaned["grupo_nombre"] = (cleaned.get("grupo_nombre") or "").strip()
        if cleaned.get("stock_actual") is None:
            cleaned["stock_actual"] = cleaned.get("unidades_compra") or 0
        if cleaned.get("stock_minimo") is None:
            cleaned["stock_minimo"] = 0
        if cleaned.get("ieps_porcentaje") is None:
            cleaned["ieps_porcentaje"] = config.ieps_predeterminado
        if cleaned.get("iva_porcentaje") is None:
            cleaned["iva_porcentaje"] = config.iva_predeterminado
        return cleaned

    def save(self, commit=True):
        producto = super().save(commit=False)
        producto.costo_compra = self.cleaned_data["costo_compra"]
        producto.unidades_compra = self.cleaned_data["unidades_compra"]
        producto.margen_porcentaje = self.cleaned_data["margen_porcentaje"]
        producto.stock_actual = self.cleaned_data["stock_actual"]
        producto.stock_minimo = self.cleaned_data["stock_minimo"]
        producto.iva_porcentaje = self.cleaned_data["iva_porcentaje"]
        producto.ieps_porcentaje = self.cleaned_data["ieps_porcentaje"]
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


class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = ["nombre", "rfc", "contacto", "telefono", "email", "direccion", "notas", "activo"]
        widgets = {"notas": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css = "form-check-input" if name == "activo" else "form-control"
            field.widget.attrs.setdefault("class", css)


class CompraForm(forms.ModelForm):
    class Meta:
        model = Compra
        fields = ["proveedor", "documento", "notas"]
        widgets = {
            "documento": forms.TextInput(attrs={"placeholder": "Factura, remisión o nota"}),
            "notas": forms.TextInput(attrs={"placeholder": "Observaciones opcionales"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["proveedor"].queryset = Proveedor.objects.filter(activo=True).order_by("nombre")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class CompraItemForm(forms.ModelForm):
    class Meta:
        model = CompraItem
        fields = ["producto", "cantidad_presentaciones", "factor_conversion", "costo_total"]
        widgets = {
            "cantidad_presentaciones": forms.NumberInput(attrs={"min": "0.001", "step": "0.001"}),
            "factor_conversion": forms.NumberInput(attrs={"min": "0.001", "step": "0.001"}),
            "costo_total": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["producto"].queryset = Producto.objects.filter(activo=True).order_by("nombre")
        self.fields["factor_conversion"].initial = self.fields["factor_conversion"].initial or 1
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class BaseCompraItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        productos = set()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            producto = form.cleaned_data.get("producto")
            if not producto:
                continue
            if producto.pk in productos:
                raise forms.ValidationError(f"El producto {producto.nombre} aparece más de una vez.")
            productos.add(producto.pk)


CompraItemFormSet = inlineformset_factory(
    Compra,
    CompraItem,
    form=CompraItemForm,
    formset=BaseCompraItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
