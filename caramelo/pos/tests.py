from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Producto
from core.models import ConfiguracionNegocio
from sales.models import CajaTurno, ClienteFiscal, MovimientoInventario, Venta, VentaSinStock


class PosCheckoutFiscalTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("caja", password="pass")
        self.client.force_login(self.user)
        self.turno = CajaTurno.objects.create(usuario=self.user, fondo_inicial=Decimal("100.00"))

    def test_raiz_redirige_al_pos(self):
        response = self.client.get("/")

        self.assertRedirects(response, reverse("pos_home"), fetch_redirect_response=False)

    def test_checkout_producto_kg_con_cliente_moral_aplica_isr_y_descuenta_stock_decimal(self):
        ConfiguracionNegocio.objects.create(aplicar_retencion_persona_moral=True)
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

    def test_escanear_barcode_agrega_e_incrementa_producto(self):
        producto = Producto.objects.create(
            nombre="Aceite",
            barcode="7501234567890",
            precio_con_iva=Decimal("42.00"),
            stock_actual=Decimal("10.000"),
        )

        primera = self.client.get(reverse("pos_home"), {"q": producto.barcode})
        segunda = self.client.get(reverse("pos_home"), {"q": producto.barcode})

        self.assertRedirects(primera, reverse("pos_home"), fetch_redirect_response=False)
        self.assertRedirects(segunda, reverse("pos_home"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["cart"][str(producto.id)], "2")

    def test_pos_muestra_identidad_configurada(self):
        ConfiguracionNegocio.objects.create(nombre_comercial="Abarrotes La Esquina")

        response = self.client.get(reverse("pos_home"))

        self.assertContains(response, "Abarrotes La Esquina")

    def test_checkout_permite_stock_insuficiente_reporta_faltante_y_mantiene_cero(self):
        ConfiguracionNegocio.objects.create(permitir_venta_sin_stock=True)
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

    def test_checkout_bloquea_stock_insuficiente_por_defecto(self):
        producto = Producto.objects.create(
            nombre="Arroz",
            precio_con_iva=Decimal("20.00"),
            stock_actual=Decimal("0.000"),
        )
        session = self.client.session
        session["cart"] = {str(producto.id): "1"}
        session.save()

        response = self.client.post(reverse("pos_checkout"), {"metodo_pago": "EFECTIVO", "efectivo_recibido": "20"})

        self.assertRedirects(response, reverse("pos_home"))
        self.assertFalse(Venta.objects.exists())

    def test_checkout_efectivo_guarda_recibido_y_cambio(self):
        producto = Producto.objects.create(
            nombre="Leche",
            precio_con_iva=Decimal("24.50"),
            stock_actual=Decimal("2.000"),
        )
        session = self.client.session
        session["cart"] = {str(producto.id): "1"}
        session.save()

        self.client.post(reverse("pos_checkout"), {"metodo_pago": "EFECTIVO", "efectivo_recibido": "50"})

        venta = Venta.objects.get()
        self.assertEqual(venta.efectivo_recibido, Decimal("50.00"))
        self.assertEqual(venta.cambio, Decimal("25.50"))
        self.assertEqual(venta.items.get().costo_unitario, Decimal("0.00"))

    def test_admin_cancela_venta_y_restituye_inventario(self):
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])
        producto = Producto.objects.create(
            nombre="Frijol",
            precio_con_iva=Decimal("30.00"),
            stock_actual=Decimal("5.000"),
        )
        session = self.client.session
        session["cart"] = {str(producto.id): "2"}
        session.save()
        self.client.post(reverse("pos_checkout"), {"metodo_pago": "EFECTIVO", "efectivo_recibido": "100"})
        venta = Venta.objects.get()

        response = self.client.post(
            reverse("venta_cancelar", kwargs={"venta_id": venta.id}),
            {"motivo": "Captura incorrecta"},
        )

        self.assertRedirects(response, reverse("pos_home"))
        venta.refresh_from_db()
        producto.refresh_from_db()
        self.assertEqual(venta.estatus, "CANCELADA")
        self.assertEqual(producto.stock_actual, Decimal("5.000"))
        self.assertTrue(MovimientoInventario.objects.filter(producto=producto, tipo="CANCELACION", cantidad=Decimal("2.000")).exists())
