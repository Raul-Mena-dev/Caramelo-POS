from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from django.urls import reverse
from django.contrib import messages

from catalog.models import Producto
from sales.models import Venta, VentaItem, MovimientoInventario
from sales.models import CajaTurno

def _get_cart(session):
    return session.setdefault("cart", {})  # {producto_id: "cantidad"}

def _cart_total(cart):
    # total se recalcula al vuelo
    total = Decimal("0.00")
    items = []
    for pid, qty_str in cart.items():
        p = Producto.objects.filter(id=int(pid), activo=True).first()
        if not p:
            continue
        qty = Decimal(qty_str)
        subtotal = (p.precio_con_iva * qty).quantize(Decimal("0.01"))
        total += subtotal
        items.append({"producto": p, "cantidad": qty, "subtotal": subtotal})
    return total.quantize(Decimal("0.01")), items

@login_required
def pos_home(request):
    cart = _get_cart(request.session)
    total, items = _cart_total(cart)

    q = (request.GET.get("q", "") or "").strip()
    resultados = []

    if q:
        # 1) INTENTO: match exacto por barcode (scanner)
        p = Producto.objects.filter(activo=True, barcode__iexact=q).first()

        # 2) (Opcional) match exacto por SKU si quieres que también funcione
        if not p:
            p = Producto.objects.filter(activo=True, sku__iexact=q).first()

        if p:
            # Auto-agrega 1 al carrito
            current = Decimal(cart.get(str(p.id), "0"))
            cart[str(p.id)] = str(current + Decimal("1"))

            request.session.modified = True
            messages.success(request, f"Agregado: {p.nombre}")

            # Redirige sin q para que NO se queden resultados y quede listo para el siguiente escaneo
            return redirect("pos_home")

        # Si no hubo match exacto, entonces sí muestra búsqueda normal
        resultados = list(Producto.objects.filter(activo=True, nombre__icontains=q)[:20])

    return render(request, "pos/home.html", {
        "items": items,
        "total": total,
        "q": q,
        "resultados": resultados,
        "turno": _get_turno_abierto(request.user),
    })
    
@login_required
def pos_add_item(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    pid = request.POST.get("producto_id")
    qty = request.POST.get("cantidad", "1")
    if not pid:
        return HttpResponseBadRequest("producto_id requerido")

    p = get_object_or_404(Producto, id=int(pid), activo=True)
    cart = _get_cart(request.session)
    current = Decimal(cart.get(str(p.id), "0"))
    new_qty = current + Decimal(qty)
    if new_qty <= 0:
        cart.pop(str(p.id), None)
    else:
        cart[str(p.id)] = str(new_qty)

    request.session.modified = True
    return redirect("pos_home")

@login_required
@transaction.atomic
def pos_checkout(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    
    turno = _get_turno_abierto(request.user)
    if not turno:
        return HttpResponseBadRequest("No hay turno abierto. Abre caja primero.")

    metodo = request.POST.get("metodo_pago", "EFECTIVO")
    cart = _get_cart(request.session)
    total, items = _cart_total(cart)
    if not items:
        return HttpResponseBadRequest("Carrito vacío")

    # Folio simple (secuencial): max + 1
    last = Venta.objects.order_by("-folio").first()
    folio = (last.folio + 1) if last else 1

    venta = Venta.objects.create(
        folio=folio,
        metodo_pago=metodo,
        total=total,
        usuario=request.user,
        turno=turno,
    )

    # Genera items y descuenta inventario
    for it in items:
        p = it["producto"]
        qty = it["cantidad"]
        subtotal = it["subtotal"]

        VentaItem.objects.create(
            venta=venta,
            producto=p,
            cantidad=qty,
            precio_unitario_con_iva=p.precio_con_iva,
            subtotal=subtotal,
        )

        # descuenta stock y registra movimiento
        p.stock_actual = (p.stock_actual - qty)
        p.save(update_fields=["stock_actual"])

        MovimientoInventario.objects.create(
            producto=p,
            tipo="VENTA",
            cantidad=-qty,
            referencia=f"V{venta.folio}",
            usuario=request.user,
        )

    # limpia carrito
    request.session["cart"] = {}
    request.session.modified = True

    ticket_url = reverse("ticket_pdf", kwargs={"venta_id": venta.id})
    messages.success(request, f"Venta V{venta.folio} generada.")
    # mandamos ticket_url como query param
    return redirect(f"{reverse('pos_home')}?ticket={ticket_url}")

@login_required
def ticket_pdf(request, venta_id: int):
    venta = get_object_or_404(Venta, id=venta_id)
    # PDF 80mm usando reportlab
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    width = 80 * mm
    # alto dinámico: header + items + footer (aprox)
    height = (60 + (len(venta.items.all()) * 10) + 40) * mm

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="ticket_V{venta.folio}.pdf"'

    c = canvas.Canvas(response, pagesize=(width, height))
    y = height - 10*mm

    def line(txt, dy=6*mm, size=10):
        nonlocal y
        c.setFont("Helvetica", size)
        c.drawString(5*mm, y, txt[:48])
        y -= dy

    # Header
    line("Caramelo", size=14, dy=8*mm)
    line(f"Ticket: V{venta.folio}", size=10)
    line(f"Fecha: {timezone.localtime(venta.fecha).strftime('%Y-%m-%d %H:%M')}", size=9)
    line("-"*48, size=9)

    # Items
    for it in venta.items.select_related("producto").all():
        nombre = it.producto.nombre
        line(nombre, size=9, dy=5*mm)
        line(f"{it.cantidad} x ${it.precio_unitario_con_iva} = ${it.subtotal}", size=9, dy=6*mm)

    line("-"*48, size=9)
    line(f"TOTAL: ${venta.total}", size=12, dy=8*mm)
    line(f"PAGO: {venta.metodo_pago}", size=10)
    line("Gracias por su compra", size=10, dy=8*mm)

    c.showPage()
    c.save()
    return response

def _get_turno_abierto(user):
    return CajaTurno.objects.filter(usuario=user, estatus="ABIERTO").order_by("-apertura").first()

@login_required
def turno_home(request):
    turno = _get_turno_abierto(request.user)
    return render(request, "pos/turno.html", {"turno": turno})

@login_required
def turno_abrir(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    # Evita dos turnos abiertos por usuario
    if _get_turno_abierto(request.user):
        return HttpResponseBadRequest("Ya tienes un turno abierto.")

    caja = (request.POST.get("caja_nombre") or "CAJA1").strip()[:40]
    fondo = Decimal((request.POST.get("fondo_inicial") or "0").strip() or "0")

    CajaTurno.objects.create(
        caja_nombre=caja,
        usuario=request.user,
        fondo_inicial=fondo,
        estatus="ABIERTO",
    )
    return redirect("pos_home")

@login_required
def turno_cerrar(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    turno = _get_turno_abierto(request.user)
    if not turno:
        return HttpResponseBadRequest("No hay turno abierto.")

    efectivo_contado = Decimal((request.POST.get("efectivo_contado") or "0").strip() or "0")

    # Totales por método dentro del turno
    ventas = turno.ventas.filter(estatus="ACTIVA")

    total_ventas = ventas.aggregate(x=Sum("total"))["x"] or Decimal("0.00")
    total_efectivo = ventas.filter(metodo_pago="EFECTIVO").aggregate(x=Sum("total"))["x"] or Decimal("0.00")
    total_tarjeta = ventas.filter(metodo_pago="TARJETA").aggregate(x=Sum("total"))["x"] or Decimal("0.00")
    total_transfer = ventas.filter(metodo_pago="TRANSFER").aggregate(x=Sum("total"))["x"] or Decimal("0.00")

    # Efectivo esperado = fondo inicial + ventas efectivo  (si luego agregas retiros, aquí se ajusta)
    efectivo_esperado = (turno.fondo_inicial + total_efectivo).quantize(Decimal("0.01"))
    diferencia = (efectivo_contado - efectivo_esperado).quantize(Decimal("0.01"))

    turno.efectivo_contado = efectivo_contado
    turno.total_ventas = total_ventas
    turno.total_efectivo = total_efectivo
    turno.total_tarjeta = total_tarjeta
    turno.total_transfer = total_transfer
    turno.diferencia_efectivo = diferencia
    turno.estatus = "CERRADO"
    turno.cierre = timezone.now()
    turno.save()

    return redirect("corte_turno", turno_id=turno.id)
