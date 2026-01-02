from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # 👈 esto
    path("pos/", include("pos.urls")),
    path("reports/", include("reports.urls")),
    path("catalog/", include("catalog.urls")),
]
