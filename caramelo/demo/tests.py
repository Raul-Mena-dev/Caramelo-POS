from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from catalog.models import Producto, Proveedor
from sales.models import Venta


class DemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_seed_creates_safe_and_useful_demo(self):
        user = get_user_model().objects.get(username=settings.DEMO_USERNAME)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.groups.filter(name="Administradores").exists())
        self.assertGreaterEqual(Producto.objects.count(), 10)
        self.assertGreaterEqual(Proveedor.objects.count(), 2)
        self.assertGreaterEqual(Venta.objects.count(), 2)

    def test_landing_and_one_click_login(self):
        response = self.client.get(reverse("demo_landing"))
        self.assertContains(response, "Demostración interactiva")
        response = self.client.post(reverse("demo_login"))
        self.assertRedirects(response, reverse("pos_home"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), get_user_model().objects.get(username=settings.DEMO_USERNAME).pk)

    def test_reset_keeps_demo_user_logged_in(self):
        self.client.post(reverse("demo_login"))
        response = self.client.post(reverse("demo_reset"))
        self.assertRedirects(response, reverse("pos_home"))
        self.assertIn("_auth_user_id", self.client.session)
