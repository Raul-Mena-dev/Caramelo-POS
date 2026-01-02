from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render
from django.utils import timezone
from django.shortcuts import get_object_or_404
from sales.models import CajaTurno, Venta, VentaItem

from sales.models import Venta, VentaItem


def _parse_date(s: str):
    """
    Espera formato YYYY-MM-DD (input type="date").
    Devuelve date o None si inválido.
    """
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def _get_range(request):
    """
    Obtiene rango de fechas (inclusive) desde query params:
    ?start=YYYY-MM-DD&end=YYYY-MM-DD

    Si no viene, usa HOY.
    """
    start_str = (request.GET.get("start") or "").strip()
    end_str = (request.GET.get("end") or "").strip()

    start_date = _parse_date(start_str)
    end_date = _parse_date(end_str)

    hoy = timezone.localdate()
    if not start_date:
        start_date = hoy
    if not end_date:
        end_date = hoy

    # Si vienen invertidas, intercambia
    if end_date < start_date:
        start_date, end_date = end_date, start_date

    # Rango datetime aware (incluye todo el día)
    tz = timezone.get_current_timezone()
    inicio = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    fin = timezone.make_aware(datetime.combine(end_date, time.max), tz)

    return start_date, end_date, inicio, fin


def _build_corte(inicio, fin):
    ventas = Venta.objects.filter(fecha__range=(inicio, fin), estatus="ACTIVA")

    totales = ventas.aggregate(total=Sum("total"), tickets=Count("id"))
    total_val = totales["total"] or Decimal("0.00")
    tickets_val = totales["tickets"] or 0
    promedio = (total_val / tickets_val) if tickets_val else Decimal("0.00")

    por_metodo = list(
        ventas.values("metodo_pago")
        .annotate(total=Sum("total"), tickets=Count("id"))
        .order_by("-total")
    )

    top = list(
        VentaItem.objects.filter(venta__in=ventas)
        .values("producto__nombre")
        .annotate(cantidad=Sum("cantidad"), dinero=Sum("subtotal"))
        .order_by("-cantidad")[:10]
    )

    return ventas, totales, promedio, por_metodo, top


@login_required
def corte_diario(request):
    start_date, end_date, inicio, fin = _get_range(request)
    ventas, totales, promedio, por_metodo, top = _build_corte(inicio, fin)

    return render(request, "reports/diario.html", {
        "start_date": start_date,
        "end_date": end_date,
        "totales": totales,
        "promedio": promedio,
        "por_metodo": por_metodo,
        "top": top,
    })


@login_required
def corte_diario_pdf(request):
    start_date, end_date, inicio, fin = _get_range(request)
    ventas, totales, promedio, por_metodo, top = _build_corte(inicio, fin)

    # PDF (formato carta)
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch

    response = render_pdf_corte(
        start_date=start_date,
        end_date=end_date,
        totales=totales,
        promedio=promedio,
        por_metodo=por_metodo,
        top=top,
    )
    return response


def render_pdf_corte(*, start_date, end_date, totales, promedio, por_metodo, top):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    width, height = letter
    resp = __import__("django.http").http.HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="corte_{start_date}_{end_date}.pdf"'

    c = canvas.Canvas(resp, pagesize=letter)

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Caramelo - Corte de ventas")
    y -= 22

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Rango: {start_date} a {end_date}")
    y -= 18

    total_val = totales["total"] or 0
    tickets_val = totales["tickets"] or 0

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Total vendido: ${total_val}")
    y -= 16
    c.drawString(50, y, f"Tickets: {tickets_val}")
    y -= 16
    c.drawString(50, y, f"Ticket promedio: ${round(promedio, 2)}")
    y -= 22

    # Por método
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Por método de pago")
    y -= 14
    c.setFont("Helvetica", 10)

    if not por_metodo:
        c.drawString(50, y, "Sin ventas en el rango.")
        y -= 14
    else:
        for r in por_metodo:
            c.drawString(50, y, f"- {r['metodo_pago']}: ${r['total']}  (tickets: {r['tickets']})")
            y -= 14
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

    y -= 10

    # Top productos
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Top productos (cantidad)")
    y -= 14
    c.setFont("Helvetica", 10)

    if not top:
        c.drawString(50, y, "Sin ventas en el rango.")
        y -= 14
    else:
        for idx, r in enumerate(top, start=1):
            nombre = r["producto__nombre"]
            cantidad = r["cantidad"]
            dinero = r["dinero"]
            c.drawString(50, y, f"{idx}. {nombre} | cant: {cantidad} | $ {dinero}")
            y -= 14
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)

    c.showPage()
    c.save()
    return resp

@login_required
def corte_turno(request, turno_id: int):
    turno = get_object_or_404(CajaTurno, id=turno_id)

    ventas = turno.ventas.filter(estatus="ACTIVA")
    totales = ventas.aggregate(total=Sum("total"), tickets=Count("id"))
    total_val = totales["total"] or 0
    tickets_val = totales["tickets"] or 0
    promedio = (total_val / tickets_val) if tickets_val else 0

    por_metodo = list(
        ventas.values("metodo_pago").annotate(total=Sum("total"), tickets=Count("id")).order_by("-total")
    )

    top = list(
        VentaItem.objects.filter(venta__in=ventas)
        .values("producto__nombre")
        .annotate(cantidad=Sum("cantidad"), dinero=Sum("subtotal"))
        .order_by("-cantidad")[:10]
    )

    return render(request, "reports/turno.html", {
        "turno": turno,
        "totales": totales,
        "promedio": promedio,
        "por_metodo": por_metodo,
        "top": top,
    })


@login_required
def corte_turno_pdf(request, turno_id: int):
    turno = get_object_or_404(CajaTurno, id=turno_id)
    ventas = turno.ventas.filter(estatus="ACTIVA")

    totales = ventas.aggregate(total=Sum("total"), tickets=Count("id"))
    total_val = totales["total"] or 0
    tickets_val = totales["tickets"] or 0
    promedio = (total_val / tickets_val) if tickets_val else 0
    por_metodo = list(ventas.values("metodo_pago").annotate(total=Sum("total"), tickets=Count("id")).order_by("-total"))
    top = list(
        VentaItem.objects.filter(venta__in=ventas)
        .values("producto__nombre")
        .annotate(cantidad=Sum("cantidad"), dinero=Sum("subtotal"))
        .order_by("-cantidad")[:10]
    )

    # Reusa tu generador de PDF (puedes copiar el render_pdf_corte y adaptar título)
    from django.http import HttpResponse
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="corte_turno_{turno.id}.pdf"'

    c = canvas.Canvas(resp, pagesize=letter)
    width, height = letter
    y = height - 50

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Caramelo - Corte por turno")
    y -= 20

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Caja: {turno.caja_nombre}  Usuario: {turno.usuario.username}")
    y -= 14
    c.drawString(50, y, f"Apertura: {turno.apertura}  Cierre: {turno.cierre or '—'}")
    y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Total vendido: ${totales['total'] or 0}")
    y -= 14
    c.drawString(50, y, f"Tickets: {totales['tickets'] or 0}")
    y -= 14
    c.drawString(50, y, f"Ticket promedio: ${round(promedio, 2)}")
    y -= 18

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Por método")
    y -= 14
    c.setFont("Helvetica", 10)
    for r in por_metodo or []:
        c.drawString(50, y, f"- {r['metodo_pago']}: ${r['total']} (tickets {r['tickets']})")
        y -= 12

    y -= 10
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Top productos")
    y -= 14
    c.setFont("Helvetica", 10)
    for i, r in enumerate(top or [], start=1):
        c.drawString(50, y, f"{i}. {r['producto__nombre']} | cant {r['cantidad']} | ${r['dinero']}")
        y -= 12

    y -= 12
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Fondo inicial: ${turno.fondo_inicial}")
    y -= 14
    c.drawString(50, y, f"Efectivo contado: ${turno.efectivo_contado}")
    y -= 14
    c.drawString(50, y, f"Diferencia: ${turno.diferencia_efectivo}")

    c.showPage()
    c.save()
    return resp

