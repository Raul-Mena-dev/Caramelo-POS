from django.contrib import admin
from django.urls import include, path

from demo import views


urlpatterns = [
    path("", views.landing, name="demo_landing"),
    path("demo/entrar/", views.demo_login, name="demo_login"),
    path("demo/restablecer/", views.demo_reset, name="demo_reset"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("pos/", include("pos.urls")),
    path("reports/", include("reports.urls")),
    path("catalog/", include("catalog.urls")),
]
