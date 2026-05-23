from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from sales.models import MovimientoInventario
from sales.models import Venta, VentaItem

from .models import Producto


class ProductoPricingTests(TestCase):
    def test_calcula_precio_con_impuestos_margen_y_redondeo(self):
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
        self.assertEqual(producto.precio_con_iva, Decimal("16.00"))
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
        self.assertEqual(producto.ieps_porcentaje, Decimal("8"))
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
