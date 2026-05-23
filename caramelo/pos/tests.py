from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Producto
from sales.models import CajaTurno, ClienteFiscal, MovimientoInventario, Venta, VentaSinStock


class PosCheckoutFiscalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("caja", password="pass")
        self.client.force_login(self.user)
        self.turno = CajaTurno.objects.create(usuario=self.user, fondo_inicial=Decimal("100.00"))

    def test_checkout_producto_kg_con_cliente_moral_aplica_isr_y_descuenta_stock_decimal(self):
        producto = Producto.objects.create(
            nombre="Cafe kg",
            precio_con_iva=Decimal("116.00"),
            ieps_porcentaje=Decimal("0"),
            iva_porcentaje=Decimal("16"),
            stock_actual=Decimal("2.000"),
            unidad_venta="KG",
        )
        cliente = ClienteFiscal.objects.create(
            razon_social="Cliente SA",
            rfc="AAA010101AAA",
            tipo_persona="MORAL",
        )
        session = self.client.session
        session["cart"] = {str(producto.id): "0.250"}
        session.save()

        response = self.client.post(reverse("pos_checkout"), {
            "metodo_pago": "EFECTIVO",
            "cliente_fiscal_id": cliente.id,
        })

        self.assertEqual(response.status_code, 302)
        venta = Venta.objects.get()
        self.assertEqual(venta.subtotal_base, Decimal("25.00"))
        self.assertEqual(venta.total_iva, Decimal("4.00"))
        self.assertEqual(venta.retencion_isr, Decimal("0.31"))
        self.assertEqual(venta.total, Decimal("28.69"))

        item = venta.items.get()
        self.assertEqual(item.cantidad, Decimal("0.250"))
        self.assertEqual(item.subtotal, Decimal("29.00"))

        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, Decimal("1.750"))
        self.assertTrue(MovimientoInventario.objects.filter(producto=producto, tipo="VENTA", cantidad=Decimal("-0.250")).exists())

    def test_pos_home_renderiza_cliente_fiscal_y_producto_por_kg(self):
        Producto.objects.create(
            nombre="Cafe kg",
            precio_con_iva=Decimal("116.00"),
            stock_actual=Decimal("2.000"),
            unidad_venta="KG",
        )
        ClienteFiscal.objects.create(
            razon_social="Cliente SA",
            rfc="AAA010101AAA",
            tipo_persona="MORAL",
        )

        response = self.client.get(f"{reverse('pos_home')}?q=Cafe")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente SA")
        self.assertContains(response, "Kilogramo")

    def test_codigo_desconocido_ofrece_alta_rapida(self):
        response = self.client.get(f"{reverse('pos_home')}?q=7500000000001")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Código no encontrado")
        self.assertContains(response, reverse("catalog_producto_rapido"))

    def test_checkout_permite_stock_insuficiente_reporta_faltante_y_mantiene_cero(self):
        producto = Producto.objects.create(
            nombre="Chocolate",
            precio_con_iva=Decimal("10.00"),
            stock_actual=Decimal("0.000"),
        )
        session = self.client.session
        session["cart"] = {str(producto.id): "1"}
        session.save()

        response = self.client.post(reverse("pos_checkout"), {"metodo_pago": "EFECTIVO"})

        self.assertEqual(response.status_code, 302)
        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, Decimal("0.000"))
        faltante = VentaSinStock.objects.get(producto=producto)
        self.assertEqual(faltante.cantidad_solicitada, Decimal("1.000"))
        self.assertEqual(faltante.stock_disponible, Decimal("0.000"))
        self.assertEqual(faltante.cantidad_faltante, Decimal("1.000"))
        self.assertFalse(MovimientoInventario.objects.filter(producto=producto, tipo="VENTA").exists())
