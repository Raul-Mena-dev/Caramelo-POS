from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="pos_home", permanent=False), name="inicio"),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),  # 👈 esto
    path("pos/", include("pos.urls")),
    path("reports/", include("reports.urls")),
    path("catalog/", include("catalog.urls")),
]
