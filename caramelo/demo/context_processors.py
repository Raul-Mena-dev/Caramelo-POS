from django.conf import settings


def demo(request):
    return {
        "demo_mode": getattr(settings, "DEMO_MODE", False),
        "demo_username": getattr(settings, "DEMO_USERNAME", "demo"),
        "demo_password": getattr(settings, "DEMO_PASSWORD", ""),
    }
