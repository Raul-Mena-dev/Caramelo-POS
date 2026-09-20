from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import Compra, CompraItem, GrupoProducto, Producto, Proveedor, SubgrupoProducto
from core.models import ConfiguracionNegocio
from sales.models import CajaTurno, ClienteFiscal, FolioVenta, MovimientoInventario, Venta, VentaItem, VentaSinStock


PRODUCTOS = [
    ("Abarrotes", "Granos", "Arroz extra 1 kg", "La Cosecha", "ABR-001", "7501000000015", "PIEZA", "18.50", "29.00", "34", "8"),
    ("Abarrotes", "Granos", "Frijol negro 900 g", "El Campo", "ABR-002", "7501000000022", "PIEZA", "25.00", "39.50", "22", "6"),
    ("Abarrotes", "Enlatados", "Atun en agua 130 g", "Costa Azul", "ABR-003", "7501000000039", "PIEZA", "14.20", "23.00", "18", "5"),
    ("Bebidas", "Refrescos", "Refresco cola 600 ml", "Burbuja", "BEB-001", "7501000000046", "PIEZA", "12.00", "19.00", "40", "10"),
    ("Bebidas", "Agua", "Agua purificada 1 l", "Sierra", "BEB-002", "7501000000053", "PIEZA", "7.50", "13.00", "30", "8"),
    ("Limpieza", "Hogar", "Detergente en polvo 1 kg", "Limpio Max", "LIM-001", "7501000000060", "PIEZA", "31.00", "48.00", "15", "4"),
    ("Limpieza", "Hogar", "Cloro 1 l", "Blanco", "LIM-002", "7501000000077", "PIEZA", "9.50", "16.00", "20", "5"),
    ("Frutas y verduras", "Fruta", "Platano", "", "FRE-001", "2000000000014", "KG", "15.00", "27.90", "18.500", "4"),
    ("Frutas y verduras", "Verdura", "Jitomate saladet", "", "FRE-002", "2000000000021", "KG", "19.00", "34.90", "12.750", "3"),
    ("Pan y botanas", "Botanas", "Papas con sal 45 g", "Crujiente", "BOT-001", "7501000000084", "PIEZA", "9.00", "16.00", "28", "7"),
    ("Pan y botanas", "Pan", "Pan blanco grande", "Trigal", "PAN-001", "7501000000091", "PIEZA", "28.00", "43.00", "10", "3"),
    ("Lacteos", "Leche", "Leche entera 1 l", "Pradera", "LAC-001", "7501000000107", "PIEZA", "19.50", "28.00", "24", "6"),
]


class Command(BaseCommand):
    help = "Crea o restablece la informacion ficticia de la version demo."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Borra los datos comerciales de la demo antes de recrearlos.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not getattr(settings, "DEMO_MODE", False):
            raise CommandError("Este comando solo funciona con caramelo.settings_demo.")

        if options["reset"]:
            self._clear_business_data()

        user = self._create_user()
        self._create_configuration()
        products = self._create_catalog()
        suppliers = self._create_suppliers()
        self._create_purchase(user, products, suppliers[0])
        self._create_history(user, products)
        self.stdout.write(self.style.SUCCESS("Demo lista. Usuario: %s" % settings.DEMO_USERNAME))

    def _clear_business_data(self):
        VentaSinStock.objects.all().delete()
        MovimientoInventario.objects.all().delete()
        Venta.objects.all().delete()
        CajaTurno.objects.all().delete()
        FolioVenta.objects.all().delete()
        Compra.objects.all().delete()
        Producto.objects.all().delete()
        SubgrupoProducto.objects.all().delete()
        GrupoProducto.objects.all().delete()
        Proveedor.objects.all().delete()
        ClienteFiscal.objects.all().delete()
        ConfiguracionNegocio.objects.all().delete()

    def _create_user(self):
        group, _ = Group.objects.get_or_create(name="Administradores")
        user, _ = get_user_model().objects.get_or_create(username=settings.DEMO_USERNAME)
        user.first_name = "Usuario"
        user.last_name = "Demostracion"
        user.email = "demo@example.com"
        user.is_active = True
        user.is_staff = False
        user.is_superuser = False
        user.set_password(settings.DEMO_PASSWORD)
        user.save()
        user.groups.add(group)
        return user

    def _create_configuration(self):
        ConfiguracionNegocio.objects.update_or_create(
            pk=1,
            defaults={
                "nombre_comercial": "Abarrotes La Esquina",
                "razon_social": "Negocio de demostracion",
                "rfc": "XAXX010101000",
                "domicilio": "Centro, Ciudad de Mexico",
                "telefono": "55 0000 0000",
                "color_primario": "#0f766e",
                "color_secundario": "#134e4a",
                "mensaje_ticket": "Gracias por visitar nuestra tienda",
                "moneda": "MXN",
                "iva_predeterminado": Decimal("0"),
                "ieps_predeterminado": Decimal("0"),
                "margen_predeterminado": Decimal("30"),
                "redondeo_precios": "0.50",
                "permitir_venta_sin_stock": False,
            },
        )

    def _create_catalog(self):
        products = {}
        for group_name, subgroup_name, name, brand, sku, barcode, unit, cost, price, stock, minimum in PRODUCTOS:
            group, _ = GrupoProducto.objects.get_or_create(nombre=group_name)
            subgroup, _ = SubgrupoProducto.objects.get_or_create(grupo=group, nombre=subgroup_name)
            product, _ = Producto.objects.update_or_create(
                sku=sku,
                defaults={
                    "nombre": name,
                    "marca": brand,
                    "barcode": barcode,
                    "precio_con_iva": Decimal(price),
                    "precio_mandatorio": Decimal(price),
                    "usar_precio_mandatorio": True,
                    "costo": Decimal(cost),
                    "costo_compra": Decimal(cost),
                    "unidades_compra": Decimal("1"),
                    "precio_sin_impuestos": Decimal(price),
                    "precio_calculado": Decimal(price),
                    "margen_porcentaje": Decimal("30"),
                    "stock_actual": Decimal(stock),
                    "stock_minimo": Decimal(minimum),
                    "unidad_venta": unit,
                    "grupo": group,
                    "subgrupo": subgroup,
                    "activo": True,
                    "controla_inventario": True,
                },
            )
            products[sku] = product
        return products

    def _create_suppliers(self):
        first, _ = Proveedor.objects.update_or_create(
            nombre="Distribuidora Central",
            defaults={"contacto": "Laura Hernandez", "telefono": "55 1234 5678", "email": "ventas@example.com", "activo": True},
        )
        second, _ = Proveedor.objects.update_or_create(
            nombre="Frutas del Mercado",
            defaults={"contacto": "Miguel Torres", "telefono": "55 8765 4321", "notas": "Entrega martes y viernes", "activo": True},
        )
        return first, second

    def _create_purchase(self, user, products, supplier):
        purchase, created = Compra.objects.get_or_create(
            proveedor=supplier,
            documento="DEMO-COMPRA-001",
            defaults={"usuario": user, "notas": "Recepcion de ejemplo", "total": Decimal("0")},
        )
        if not created:
            return
        total = Decimal("0")
        for sku, quantity in (("ABR-001", Decimal("24")), ("BEB-001", Decimal("30")), ("LAC-001", Decimal("24"))):
            product = products[sku]
            line_total = product.costo * quantity
            CompraItem.objects.create(
                compra=purchase,
                producto=product,
                cantidad_presentaciones=quantity,
                factor_conversion=Decimal("1"),
                cantidad_unidades=quantity,
                costo_total=line_total,
                costo_unitario=product.costo,
                costo_promedio_resultante=product.costo,
                stock_anterior=max(product.stock_actual - quantity, Decimal("0")),
                stock_nuevo=product.stock_actual,
            )
            MovimientoInventario.objects.create(producto=product, tipo="ENTRADA", cantidad=quantity, referencia=purchase.folio, usuario=user)
            total += line_total
        purchase.total = total
        purchase.save(update_fields=["total"])
        Compra.objects.filter(pk=purchase.pk).update(fecha=timezone.now() - timedelta(days=4))

    def _create_history(self, user, products):
        if Venta.objects.filter(usuario=user).exists():
            return
        now = timezone.now()
        turn = CajaTurno.objects.create(
            caja_nombre="CAJA1",
            usuario=user,
            estatus="CERRADO",
            fondo_inicial=Decimal("500.00"),
            cierre=now - timedelta(days=1, hours=7),
        )
        CajaTurno.objects.filter(pk=turn.pk).update(apertura=now - timedelta(days=1, hours=9))
        cash_total = self._create_sale(user, turn, "EFECTIVO", [(products["ABR-001"], Decimal("1")), (products["BEB-001"], Decimal("2"))], now - timedelta(days=1, hours=8))
        card_total = self._create_sale(user, turn, "TARJETA", [(products["LAC-001"], Decimal("1")), (products["PAN-001"], Decimal("1"))], now - timedelta(days=1, hours=7, minutes=30))
        turn.total_ventas = cash_total + card_total
        turn.total_efectivo = cash_total
        turn.total_tarjeta = card_total
        turn.efectivo_contado = turn.fondo_inicial + cash_total
        turn.diferencia_efectivo = Decimal("0.00")
        turn.save(update_fields=["total_ventas", "total_efectivo", "total_tarjeta", "efectivo_contado", "diferencia_efectivo"])

    def _create_sale(self, user, turn, method, lines, sale_date):
        snapshots = []
        for product, quantity in lines:
            breakdown = product.desglose_unitario()
            snapshots.append((product, quantity, breakdown))
        subtotal_base = sum((data["base"] * quantity for _, quantity, data in snapshots), Decimal("0")).quantize(Decimal("0.01"))
        total_ieps = sum((data["ieps"] * quantity for _, quantity, data in snapshots), Decimal("0")).quantize(Decimal("0.01"))
        total_iva = sum((data["iva"] * quantity for _, quantity, data in snapshots), Decimal("0")).quantize(Decimal("0.01"))
        total = sum((data["precio"] * quantity for _, quantity, data in snapshots), Decimal("0")).quantize(Decimal("0.01"))
        sale = Venta.objects.create(
            folio=FolioVenta.siguiente(),
            metodo_pago=method,
            subtotal_base=subtotal_base,
            total_ieps=total_ieps,
            total_iva=total_iva,
            total=total,
            efectivo_recibido=total if method == "EFECTIVO" else Decimal("0"),
            usuario=user,
            turno=turn,
        )
        Venta.objects.filter(pk=sale.pk).update(fecha=sale_date)
        for product, quantity, data in snapshots:
            VentaItem.objects.create(
                venta=sale,
                producto=product,
                cantidad=quantity,
                base_unitaria=data["base"],
                ieps_unitario=data["ieps"],
                iva_unitario=data["iva"],
                precio_unitario_con_iva=data["precio"],
                base_total=(data["base"] * quantity).quantize(Decimal("0.01")),
                ieps_total=(data["ieps"] * quantity).quantize(Decimal("0.01")),
                iva_total=(data["iva"] * quantity).quantize(Decimal("0.01")),
                subtotal=(data["precio"] * quantity).quantize(Decimal("0.01")),
                costo_unitario=product.costo,
            )
        return total
