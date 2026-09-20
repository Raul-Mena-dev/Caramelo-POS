"""
ASGI config for caramelo project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

default_settings = "caramelo.settings_demo" if os.environ.get("VERCEL") else "caramelo.settings"
os.environ.setdefault('DJANGO_SETTINGS_MODULE', default_settings)

application = get_asgi_application()
