from .models import ConfiguracionNegocio


def negocio(request):
    return {"negocio": ConfiguracionNegocio.cargar()}
