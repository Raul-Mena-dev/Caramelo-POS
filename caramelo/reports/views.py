import csv
from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, F, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.utils import timezone
from core.models import ConfiguracionNegocio
from catalog.models import Producto
from sales.models import CajaTurno, Venta, VentaItem, VentaSinStock


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
    items_contables = VentaItem.objects.filter(
        venta__in=ventas,
        producto__no_contabilizable=False,
    )

    costo_output = DecimalField(max_digits=18, decimal_places=2)
    totales = items_contables.aggregate(
        total=Sum("subtotal"),
        tickets=Count("venta", distinct=True),
        subtotal_base=Sum("base_total"),
        total_ieps=Sum("ieps_total"),
        total_iva=Sum("iva_total"),
        costo=Sum(F("costo_unitario") * F("cantidad"), output_field=costo_output),
    )
    total_val = totales["total"] or Decimal("0.00")
    costo_val = totales["costo"] or Decimal("0.00")
    utilidad = (total_val - costo_val).quantize(Decimal("0.01"))
    totales["costo"] = costo_val.quantize(Decimal("0.01"))
    totales["utilidad"] = utilidad
    totales["margen"] = ((utilidad / total_val) * Decimal("100")).quantize(Decimal("0.01")) if total_val else Decimal("0.00")
    tickets_val = totales["tickets"] or 0
    promedio = (total_val / tickets_val) if tickets_val else Decimal("0.00")

    por_metodo = list(
        items_contables.values("venta__metodo_pago")
        .annotate(total=Sum("subtotal"), tickets=Count("venta", distinct=True))
        .order_by("-total")
    )

    top = list(
        items_contables
        .values("producto__nombre")
        .annotate(
            unidades_vendidas=Sum("cantidad"),
            dinero=Sum("subtotal"),
            costo=Sum(F("costo_unitario") * F("cantidad"), output_field=DecimalField(max_digits=18, decimal_places=2)),
        )
        .order_by("-unidades_vendidas")[:10]
    )
    for row in top:
        row["cantidad"] = row["unidades_vendidas"]
        row["costo"] = row["costo"] or Decimal("0.00")
        row["utilidad"] = (row["dinero"] - row["costo"]).quantize(Decimal("0.01"))

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

    response = render_pdf_corte(
        start_date=start_date,
        end_date=end_date,
        totales=totales,
        promedio=promedio,
        por_metodo=por_metodo,
        top=top,
    )
    return response


@login_required
def corte_diario_csv(request):
    start_date, end_date, inicio, fin = _get_range(request)
    items = (
        VentaItem.objects.filter(
            venta__fecha__range=(inicio, fin),
            venta__estatus="ACTIVA",
            producto__no_contabilizable=False,
        )
        .select_related("venta", "producto", "venta__cliente_fiscal")
        .order_by("venta__fecha", "venta__folio", "id")
    )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="corte_{start_date}_{end_date}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "fecha",
        "folio",
        "metodo_pago",
        "cliente",
        "rfc",
        "producto",
        "cantidad",
        "base",
        "ieps",
        "iva",
        "subtotal",
        "costo",
        "utilidad",
        "retencion_isr_venta",
        "total_venta",
    ])
    for item in items:
        cliente = item.venta.cliente_fiscal
        costo_total = (item.costo_unitario * item.cantidad).quantize(Decimal("0.01"))
        utilidad = (item.subtotal - costo_total).quantize(Decimal("0.01"))
        writer.writerow([
            timezone.localtime(item.venta.fecha).strftime("%Y-%m-%d %H:%M"),
            item.venta.folio,
            item.venta.metodo_pago,
            cliente.razon_social if cliente else "Publico general",
            cliente.rfc if cliente else "",
            item.producto.nombre,
            item.cantidad,
            item.base_total,
            item.ieps_total,
            item.iva_total,
            item.subtotal,
            costo_total,
            utilidad,
            item.venta.retencion_isr,
            item.venta.total,
        ])
    return response


@login_required
def ventas_sin_stock(request):
    start_date, end_date, inicio, fin = _get_range(request)
    faltantes = (
        VentaSinStock.objects.filter(fecha__range=(inicio, fin))
        .select_related("venta", "producto", "usuario")
        .order_by("-fecha")
    )
    totales = faltantes.aggregate(cantidad=Sum("cantidad_faltante"), eventos=Count("id"))
    return render(request, "reports/sin_stock.html", {
        "start_date": start_date,
        "end_date": end_date,
        "faltantes": faltantes,
        "totales": totales,
    })


@login_required
def ventas_sin_stock_csv(request):
    start_date, end_date, inicio, fin = _get_range(request)
    faltantes = (
        VentaSinStock.objects.filter(fecha__range=(inicio, fin))
        .select_related("venta", "producto", "usuario")
        .order_by("fecha")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="ventas_sin_stock_{start_date}_{end_date}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow([
        "fecha",
        "folio",
        "producto",
        "cantidad_solicitada",
        "stock_disponible",
        "cantidad_faltante",
        "usuario",
    ])
    for row in faltantes:
        writer.writerow([
            timezone.localtime(row.fecha).strftime("%Y-%m-%d %H:%M"),
            row.venta.folio,
            row.producto.nombre,
            row.cantidad_solicitada,
            row.stock_disponible,
            row.cantidad_faltante,
            row.usuario.username,
        ])
    return response


def render_pdf_corte(*, start_date, end_date, totales, promedio, por_metodo, top):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    width, height = letter
    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="corte_{start_date}_{end_date}.pdf"'

    c = canvas.Canvas(resp, pagesize=letter)

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"{ConfiguracionNegocio.cargar().nombre_comercial} - Corte de ventas")
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

    c.drawString(50, y, f"Costo: ${totales.get('costo') or 0}  Utilidad: ${totales.get('utilidad') or 0}  Margen: {totales.get('margen') or 0}%")
    y -= 18

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Base: ${totales.get('subtotal_base') or 0}  IEPS: ${totales.get('total_ieps') or 0}  IVA: ${totales.get('total_iva') or 0}")
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
            c.drawString(50, y, f"- {r['venta__metodo_pago']}: ${r['total']}  (tickets: {r['tickets']})")
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


def _inventario_valorizado():
    filas = []
    costo_total = Decimal("0.00")
    venta_total = Decimal("0.00")
    for producto in Producto.objects.filter(activo=True, controla_inventario=True).select_related("grupo").order_by("nombre"):
        stock = max(producto.stock_actual, Decimal("0.000"))
        valor_costo = (stock * producto.costo).quantize(Decimal("0.01"))
        valor_venta = (stock * producto.precio_con_iva).quantize(Decimal("0.01"))
        utilidad = (valor_venta - valor_costo).quantize(Decimal("0.01"))
        costo_total += valor_costo
        venta_total += valor_venta
        filas.append({
            "producto": producto,
            "stock": stock,
            "valor_costo": valor_costo,
            "valor_venta": valor_venta,
            "utilidad": utilidad,
        })
    return filas, {
        "productos": len(filas),
        "costo": costo_total.quantize(Decimal("0.01")),
        "venta": venta_total.quantize(Decimal("0.01")),
        "utilidad": (venta_total - costo_total).quantize(Decimal("0.01")),
    }


@login_required
def inventario_valorizado(request):
    if not (request.user.is_superuser or request.user.groups.filter(name="Administradores").exists()):
        return HttpResponseForbidden("No autorizado.")
    filas, totales = _inventario_valorizado()
    return render(request, "reports/inventario_valorizado.html", {"filas": filas, "totales": totales})


@login_required
def inventario_valorizado_csv(request):
    if not (request.user.is_superuser or request.user.groups.filter(name="Administradores").exists()):
        return HttpResponseForbidden("No autorizado.")
    filas, _totales = _inventario_valorizado()
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="inventario_valorizado.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["producto", "categoria", "stock", "unidad", "costo_unitario", "precio_venta", "valor_costo", "valor_venta", "utilidad_potencial"])
    for fila in filas:
        producto = fila["producto"]
        writer.writerow([
            producto.nombre,
            producto.grupo.nombre if producto.grupo else "",
            fila["stock"],
            producto.get_unidad_venta_display(),
            producto.costo,
            producto.precio_con_iva,
            fila["valor_costo"],
            fila["valor_venta"],
            fila["utilidad"],
        ])
    return response

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
    c.drawString(50, y, f"{ConfiguracionNegocio.cargar().nombre_comercial} - Corte por turno")
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
