from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST


def _ensure_demo_mode():
    if not getattr(settings, "DEMO_MODE", False):
        raise Http404


def landing(request):
    _ensure_demo_mode()
    return render(request, "demo/landing.html")


@require_POST
def demo_login(request):
    _ensure_demo_mode()
    user = get_user_model().objects.filter(username=settings.DEMO_USERNAME, is_active=True).first()
    if not user:
        messages.error(request, "La demo aun no ha sido inicializada.")
        return redirect("demo_landing")
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["cart"] = {}
    return redirect("pos_home")


@login_required
@require_POST
def demo_reset(request):
    _ensure_demo_mode()
    if request.user.username != settings.DEMO_USERNAME:
        return HttpResponseForbidden("Solo el usuario de demostracion puede restablecer estos datos.")
    call_command("seed_demo", reset=True, verbosity=0)
    request.user.refresh_from_db()
    login(request, request.user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["cart"] = {}
    messages.success(request, "La demostracion recupero sus datos iniciales.")
    return redirect("pos_home")
