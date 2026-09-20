from django.contrib import admin

from .models import ConfiguracionNegocio


@admin.register(ConfiguracionNegocio)
class ConfiguracionNegocioAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Identidad", {"fields": ("nombre_comercial", "razon_social", "rfc", "domicilio", "telefono", "logo_url")} ),
        ("Apariencia", {"fields": ("color_primario", "color_secundario")} ),
        ("Precios", {"fields": ("moneda", "iva_predeterminado", "ieps_predeterminado", "margen_predeterminado", "redondeo_precios")} ),
        ("Operacion", {"fields": ("permitir_venta_sin_stock", "mensaje_ticket")} ),
        ("Fiscal", {"fields": ("aplicar_retencion_persona_moral", "retencion_persona_moral")} ),
    )

    def has_add_permission(self, request):
        return not ConfiguracionNegocio.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
