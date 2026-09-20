from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from sales.models import MovimientoInventario
from sales.models import Venta, VentaItem
from core.models import ConfiguracionNegocio

from .models import Compra, CompraItem, Producto, Proveedor


class ProductoPricingTests(TestCase):
    def test_calcula_precio_con_impuestos_margen_y_redondeo(self):
        ConfiguracionNegocio.objects.create(redondeo_precios="0.50")
        producto = Producto(
            nombre="Dulce por pieza",
            costo_compra=Decimal("40.00"),
            unidades_compra=Decimal("100"),
            ieps_porcentaje=Decimal("8"),
            iva_porcentaje=Decimal("16"),
            margen_porcentaje=Decimal("35"),
        )

        producto.calcular_precio()

        self.assertEqual(producto.costo, Decimal("0.40"))
        self.assertEqual(producto.precio_sin_impuestos, Decimal("0.54"))
        self.assertEqual(producto.precio_calculado, Decimal("0.68"))
        self.assertEqual(producto.precio_con_iva, Decimal("1.00"))

    def test_respeta_precio_mandatorio(self):
        producto = Producto(
            nombre="Precio fijo",
            costo_compra=Decimal("40.00"),
            unidades_compra=Decimal("100"),
            precio_mandatorio=Decimal("5.00"),
            usar_precio_mandatorio=True,
        )

        producto.calcular_precio()

        self.assertEqual(producto.precio_con_iva, Decimal("5.00"))


class EntradaCompraTests(TestCase):
    def test_compra_formal_con_varias_partidas_actualiza_stock_y_costos(self):
        user = get_user_model().objects.create_superuser("compras", "compras@example.com", "pass")
        proveedor = Proveedor.objects.create(nombre="Distribuidora Centro")
        aceite = Producto.objects.create(nombre="Aceite", precio_con_iva=Decimal("20.00"), stock_actual=Decimal("1.000"))
        arroz = Producto.objects.create(nombre="Arroz", precio_con_iva=Decimal("10.00"), stock_actual=Decimal("0.000"))
        self.client.force_login(user)

        response = self.client.post(reverse("catalog_compra_nueva"), {
            "proveedor": proveedor.id,
            "documento": "FAC-22",
            "notas": "Entrega completa",
            "items-TOTAL_FORMS": "2",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-producto": aceite.id,
            "items-0-cantidad_presentaciones": "2",
            "items-0-factor_conversion": "12",
            "items-0-costo_total": "120.00",
            "items-1-producto": arroz.id,
            "items-1-cantidad_presentaciones": "5",
            "items-1-factor_conversion": "1",
            "items-1-costo_total": "30.00",
        })

        compra = Compra.objects.get()
        self.assertRedirects(response, reverse("catalog_compra_detalle", kwargs={"compra_id": compra.id}))
        self.assertEqual(compra.total, Decimal("150.00"))
        self.assertEqual(CompraItem.objects.filter(compra=compra).count(), 2)
        self.assertEqual(CompraItem.objects.get(compra=compra, producto=aceite).costo_promedio_resultante, Decimal("4.80"))
        aceite.refresh_from_db()
        arroz.refresh_from_db()
        self.assertEqual(aceite.stock_actual, Decimal("25.000"))
        self.assertEqual(aceite.costo, Decimal("4.80"))
        self.assertEqual(arroz.stock_actual, Decimal("5.000"))
        self.assertEqual(arroz.costo, Decimal("6.00"))
        self.assertEqual(MovimientoInventario.objects.filter(tipo="ENTRADA", referencia="FAC-22").count(), 2)

    def test_pantalla_nueva_compra_renderiza_formset(self):
        user = get_user_model().objects.create_superuser("compras_ui", "compras-ui@example.com", "pass")
        Proveedor.objects.create(nombre="Proveedor UI")
        Producto.objects.create(nombre="Producto UI", precio_con_iva=Decimal("10.00"))
        self.client.force_login(user)

        response = self.client.get(reverse("catalog_compra_nueva"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "id_items-TOTAL_FORMS")
        self.assertContains(response, "Recibir compra y actualizar inventario")

    def test_entrada_compra_suma_stock_actualiza_precio_y_crea_movimiento(self):
        user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pass")
        producto = Producto.objects.create(
            nombre="Azucar",
            precio_con_iva=Decimal("1.00"),
            stock_actual=Decimal("1.000"),
        )
        self.client.force_login(user)

        response = self.client.post(reverse("catalog_entrada_compra"), {
            "producto": producto.id,
            "cantidad": "2.500",
            "costo_compra": "100.00",
            "unidades_compra": "10",
            "ieps_porcentaje": "0",
            "iva_porcentaje": "16",
            "margen_porcentaje": "35",
            "referencia": "FAC-1",
        })

        self.assertRedirects(response, reverse("catalog_inventario"))
        producto.refresh_from_db()
        self.assertEqual(producto.stock_actual, Decimal("3.500"))
        self.assertEqual(producto.precio_con_iva, Decimal("15.66"))
        self.assertTrue(MovimientoInventario.objects.filter(producto=producto, tipo="ENTRADA", referencia="FAC-1").exists())

    def test_producto_rapido_crea_producto_con_barcode_precargado(self):
        user = get_user_model().objects.create_superuser("admin2", "admin2@example.com", "pass")
        self.client.force_login(user)

        response = self.client.post(reverse("catalog_producto_rapido"), {
            "barcode": "7501234567890",
            "nombre": "Paleta",
            "precio_con_iva": "5.00",
            "costo_compra": "20.00",
            "unidades_compra": "10",
            "margen_porcentaje": "35",
            "stock_actual": "",
            "stock_minimo": "2",
            "unidad_venta": "PIEZA",
            "grupo_nombre": "Paletas",
            "next": reverse("catalog_inventario"),
        })

        self.assertRedirects(response, reverse("catalog_inventario"))
        producto = Producto.objects.get(barcode="7501234567890")
        self.assertEqual(producto.nombre, "Paleta")
        self.assertEqual(producto.precio_con_iva, Decimal("5.00"))
        self.assertEqual(producto.ieps_porcentaje, Decimal("0"))
        self.assertEqual(producto.stock_actual, Decimal("10.000"))
        self.assertEqual(producto.stock_minimo, Decimal("2.000"))

    def test_borrar_producto_sin_historial_lo_elimina(self):
        user = get_user_model().objects.create_superuser("admin3", "admin3@example.com", "pass")
        producto = Producto.objects.create(nombre="Temporal", precio_con_iva=Decimal("3.00"))
        self.client.force_login(user)

        response = self.client.post(reverse("catalog_producto_borrar", kwargs={"producto_id": producto.id}))

        self.assertRedirects(response, reverse("catalog_inventario"))
        self.assertFalse(Producto.objects.filter(id=producto.id).exists())

    def test_borrar_producto_con_historial_lo_desactiva(self):
        user = get_user_model().objects.create_superuser("admin4", "admin4@example.com", "pass")
        producto = Producto.objects.create(nombre="Con historial", precio_con_iva=Decimal("3.00"))
        venta = Venta.objects.create(folio=99, metodo_pago="EFECTIVO", total=Decimal("3.00"), usuario=user)
        VentaItem.objects.create(
            venta=venta,
            producto=producto,
            cantidad=Decimal("1"),
            precio_unitario_con_iva=Decimal("3.00"),
            subtotal=Decimal("3.00"),
        )
        self.client.force_login(user)

        response = self.client.post(reverse("catalog_producto_borrar", kwargs={"producto_id": producto.id}))

        self.assertRedirects(response, reverse("catalog_inventario"))
        producto.refresh_from_db()
        self.assertFalse(producto.activo)

    def test_inventario_localiza_producto_por_barcode(self):
        user = get_user_model().objects.create_superuser("admin5", "admin5@example.com", "pass")
        Producto.objects.create(nombre="Producto escaneado", barcode="7509999999999", precio_con_iva=Decimal("12.00"))
        Producto.objects.create(nombre="Producto diferente", barcode="7501111111111", precio_con_iva=Decimal("15.00"))
        self.client.force_login(user)

        response = self.client.get(reverse("catalog_inventario"), {"q": "7509999999999"})

        self.assertContains(response, "Producto escaneado")
        self.assertNotContains(response, "Producto diferente")
