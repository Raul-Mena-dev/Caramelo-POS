"""Configuracion aislada para la demostracion publica en Vercel."""

import os
from urllib.parse import parse_qs, unquote, urlparse

from .settings import *  # noqa: F403


DEMO_MODE = True
DEMO_USERNAME = os.environ.get("POS_DEMO_USERNAME", "demo")
DEMO_PASSWORD = os.environ.get("POS_DEMO_PASSWORD", "DemoPOS2026!")

DEBUG = False
ROOT_URLCONF = "caramelo.urls_demo"
INSTALLED_APPS = [*INSTALLED_APPS, "demo"]  # noqa: F405
TEMPLATES[0]["OPTIONS"]["context_processors"].append("demo.context_processors.demo")  # noqa: F405

ALLOWED_HOSTS = sorted(set([*ALLOWED_HOSTS, ".vercel.app", "127.0.0.1", "localhost"]))  # noqa: F405
for variable in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    host = os.environ.get(variable, "").strip()
    if host:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = [
    f"https://{'*' + host if host.startswith('.') else host}"
    for host in ALLOWED_HOSTS
    if host and host not in {"127.0.0.1", "localhost", ".vercel.app"}
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if os.environ.get("VERCEL"):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

LOGIN_REDIRECT_URL = "/pos/"
LOGOUT_REDIRECT_URL = "/"


def _database_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql_psycopg2"}:
        raise ValueError("DATABASE_URL debe apuntar a PostgreSQL.")
    query = parse_qs(parsed.query)
    options = {}
    if "sslmode" in query:
        options["sslmode"] = query["sslmode"][-1]
    elif os.environ.get("VERCEL"):
        options["sslmode"] = "require"
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or "5432"),
        "CONN_MAX_AGE": 0,
        "OPTIONS": options,
    }


if os.environ.get("DATABASE_URL"):
    DATABASES = {"default": _database_from_url(os.environ["DATABASE_URL"])}
elif os.environ.get("VERCEL"):
    raise RuntimeError("La demo en Vercel necesita la variable DATABASE_URL de PostgreSQL.")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db_demo.sqlite3",  # noqa: F405
        }
    }
