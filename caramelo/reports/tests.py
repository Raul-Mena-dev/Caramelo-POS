from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Producto
from sales.models import Venta, VentaItem, VentaSinStock


class CorteCsvTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("reportes", password="pass")
        self.client.force_login(self.user)

    def test_csv_excluye_productos_no_contabilizables(self):
        producto_contable = Producto.objects.create(nombre="Contable", precio_con_iva=Decimal("10.00"))
        producto_no_contable = Producto.objects.create(
            nombre="No contable",
            precio_con_iva=Decimal("99.00"),
            no_contabilizable=True,
        )
        venta = Venta.objects.create(
            folio=1,
            metodo_pago="EFECTIVO",
            subtotal_base=Decimal("93.97"),
            total_iva=Decimal("15.03"),
            total=Decimal("109.00"),
            usuario=self.user,
        )
        VentaItem.objects.create(
            venta=venta,
            producto=producto_contable,
            cantidad=Decimal("1"),
            base_total=Decimal("8.62"),
            iva_total=Decimal("1.38"),
            precio_unitario_con_iva=Decimal("10.00"),
            subtotal=Decimal("10.00"),
        )
        VentaItem.objects.create(
            venta=venta,
            producto=producto_no_contable,
            cantidad=Decimal("1"),
            base_total=Decimal("85.35"),
            iva_total=Decimal("13.65"),
            precio_unitario_con_iva=Decimal("99.00"),
            subtotal=Decimal("99.00"),
        )

        today = timezone.localdate().strftime("%Y-%m-%d")
        response = self.client.get(f"{reverse('corte_diario_csv')}?start={today}&end={today}")

        self.assertEqual(response.status_code, 200)
        body = response.content.decode("utf-8-sig")
        self.assertIn("Contable", body)
        self.assertNotIn("No contable", body)

    def test_corte_diario_html_renderiza_metodo_y_totales_fiscales(self):
        producto = Producto.objects.create(nombre="Contable", precio_con_iva=Decimal("10.00"))
        venta = Venta.objects.create(
            folio=2,
            metodo_pago="TARJETA",
            subtotal_base=Decimal("8.62"),
            total_iva=Decimal("1.38"),
            total=Decimal("10.00"),
            usuario=self.user,
        )
        VentaItem.objects.create(
            venta=venta,
            producto=producto,
            cantidad=Decimal("1"),
            base_total=Decimal("8.62"),
            iva_total=Decimal("1.38"),
            precio_unitario_con_iva=Decimal("10.00"),
            subtotal=Decimal("10.00"),
        )

        today = timezone.localdate().strftime("%Y-%m-%d")
        response = self.client.get(f"{reverse('corte_diario')}?start={today}&end={today}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TARJETA")
        self.assertContains(response, "$8.62")

    def test_reporte_ventas_sin_stock_muestra_faltantes(self):
        producto = Producto.objects.create(nombre="Chocolate", precio_con_iva=Decimal("10.00"))
        venta = Venta.objects.create(
            folio=3,
            metodo_pago="EFECTIVO",
            total=Decimal("10.00"),
            usuario=self.user,
        )
        VentaSinStock.objects.create(
            venta=venta,
            producto=producto,
            cantidad_solicitada=Decimal("2.000"),
            stock_disponible=Decimal("0.500"),
            cantidad_faltante=Decimal("1.500"),
            usuario=self.user,
        )

        today = timezone.localdate().strftime("%Y-%m-%d")
        response = self.client.get(f"{reverse('ventas_sin_stock')}?start={today}&end={today}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chocolate")
        self.assertContains(response, "1.500")
