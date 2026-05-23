from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from django.urls import reverse
from django.contrib import messages

from catalog.models import Producto
from sales.models import ClienteFiscal, Venta, VentaItem, MovimientoInventario, VentaSinStock
from sales.models import CajaTurno

MONEY = Decimal("0.01")
RETENCION_PERSONA_MORAL = Decimal("0.0125")

def _get_cart(session):
    return session.setdefault("cart", {})  # {producto_id: "cantidad"}

def _decimal(value, default="0"):
    try:
        return Decimal(str(value or default))
    except (InvalidOperation, ValueError):
        return Decimal(default)

def _item_snapshot(producto, cantidad):
    desglose = producto.desglose_unitario()
    subtotal = (desglose["precio"] * cantidad).quantize(MONEY)
    base_total = (desglose["base"] * cantidad).quantize(MONEY)
    ieps_total = (desglose["ieps"] * cantidad).quantize(MONEY)
    iva_total = (desglose["iva"] * cantidad).quantize(MONEY)
    return {
        "producto": producto,
        "cantidad": cantidad,
        "base_unitaria": desglose["base"],
        "ieps_unitario": desglose["ieps"],
        "iva_unitario": desglose["iva"],
        "precio_unitario_con_iva": desglose["precio"],
        "base_total": base_total,
        "ieps_total": ieps_total,
        "iva_total": iva_total,
        "subtotal": subtotal,
    }

def _cart_total(cart):
    # total se recalcula al vuelo
    total = Decimal("0.00")
    items = []
    for pid, qty_str in cart.items():
        p = Producto.objects.filter(id=int(pid), activo=True).first()
        if not p:
            continue
        qty = _decimal(qty_str)
        if qty <= 0:
            continue
        item = _item_snapshot(p, qty)
        total += item["subtotal"]
        items.append(item)
    return total.quantize(Decimal("0.01")), items

@login_required
def pos_home(request):
    cart = _get_cart(request.session)
    total, items = _cart_total(cart)

    q = (request.GET.get("q", "") or "").strip()
    resultados = []
    codigo_no_encontrado = ""
    crear_producto_url = ""

    if q:
        # 1) INTENTO: match exacto por barcode (scanner)
        p = Producto.objects.filter(activo=True, barcode__iexact=q).first()

        # 2) (Opcional) match exacto por SKU si quieres que también funcione
        if not p:
            p = Producto.objects.filter(activo=True, sku__iexact=q).first()

        if p:
            # Auto-agrega 1 al carrito
            current = _decimal(cart.get(str(p.id), "0"))
            cart[str(p.id)] = str(current + Decimal("1"))

            request.session.modified = True
            messages.success(request, f"Agregado: {p.nombre}")

            # Redirige sin q para que NO se queden resultados y quede listo para el siguiente escaneo
            return redirect("pos_home")

        # Si no hubo match exacto, entonces sí muestra búsqueda normal
        resultados = list(Producto.objects.filter(activo=True, nombre__icontains=q)[:20])
        if not resultados:
            codigo_no_encontrado = q
            crear_producto_url = f"{reverse('catalog_producto_rapido')}?barcode={q}&next={reverse('pos_home')}"

    return render(request, "pos/home.html", {
        "items": items,
        "total": total,
        "q": q,
        "resultados": resultados,
        "codigo_no_encontrado": codigo_no_encontrado,
        "crear_producto_url": crear_producto_url,
        "turno": _get_turno_abierto(request.user),
        "clientes_fiscales": ClienteFiscal.objects.filter(activo=True).order_by("razon_social"),
        "ultima_venta": Venta.objects.filter(usuario=request.user).order_by("-fecha").first(),
    })
    
@login_required
def pos_add_item(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    pid = request.POST.get("producto_id")
    qty = _decimal(request.POST.get("cantidad", "1"), "1")
    if not pid:
        return HttpResponseBadRequest("producto_id requerido")
    if qty == 0:
        return redirect("pos_home")

    p = get_object_or_404(Producto, id=int(pid), activo=True)
    cart = _get_cart(request.session)
    current = _decimal(cart.get(str(p.id), "0"))
    new_qty = current + qty
    if new_qty <= 0:
        cart.pop(str(p.id), None)
    else:
        cart[str(p.id)] = str(new_qty)

    request.session.modified = True
    return redirect("pos_home")


@login_required
def pos_clear_cart(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    request.session["cart"] = {}
    request.session.modified = True
    messages.info(request, "Carrito vacío.")
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
    cliente_id = request.POST.get("cliente_fiscal_id") or None
    cliente = None
    if cliente_id:
        cliente = get_object_or_404(ClienteFiscal, id=int(cliente_id), activo=True)

    cart = _get_cart(request.session)
    total_bruto, items = _cart_total(cart)
    if not items:
        return HttpResponseBadRequest("Carrito vacío")

    subtotal_base = sum((it["base_total"] for it in items), Decimal("0.00")).quantize(MONEY)
    total_ieps = sum((it["ieps_total"] for it in items), Decimal("0.00")).quantize(MONEY)
    total_iva = sum((it["iva_total"] for it in items), Decimal("0.00")).quantize(MONEY)
    retencion_isr = Decimal("0.00")
    if cliente and cliente.tipo_persona == "MORAL":
        retencion_isr = (subtotal_base * RETENCION_PERSONA_MORAL).quantize(MONEY)
    total = (total_bruto - retencion_isr).quantize(MONEY)

    # Folio simple (secuencial): max + 1
    last = Venta.objects.order_by("-folio").first()
    folio = (last.folio + 1) if last else 1

    venta = Venta.objects.create(
        folio=folio,
        metodo_pago=metodo,
        subtotal_base=subtotal_base,
        total_ieps=total_ieps,
        total_iva=total_iva,
        retencion_isr=retencion_isr,
        total=total,
        usuario=request.user,
        turno=turno,
        cliente_fiscal=cliente,
    )

    # Genera items y descuenta inventario
    for it in items:
        p = it["producto"]
        qty = it["cantidad"]

        VentaItem.objects.create(
            venta=venta,
            producto=p,
            cantidad=qty,
            base_unitaria=it["base_unitaria"],
            ieps_unitario=it["ieps_unitario"],
            iva_unitario=it["iva_unitario"],
            precio_unitario_con_iva=it["precio_unitario_con_iva"],
            base_total=it["base_total"],
            ieps_total=it["ieps_total"],
            iva_total=it["iva_total"],
            subtotal=it["subtotal"],
        )

        disponible = p.stock_actual
        cantidad_a_descontar = min(disponible, qty)
        faltante = qty - cantidad_a_descontar

        # descuenta stock sin bajar de cero y registra incidencia si faltó producto
        p.stock_actual = max(disponible - qty, Decimal("0.000"))
        p.save(update_fields=["stock_actual"])

        if cantidad_a_descontar > 0:
            MovimientoInventario.objects.create(
                producto=p,
                tipo="VENTA",
                cantidad=-cantidad_a_descontar,
                referencia=f"V{venta.folio}",
                usuario=request.user,
            )
        if faltante > 0:
            VentaSinStock.objects.create(
                venta=venta,
                producto=p,
                cantidad_solicitada=qty,
                stock_disponible=disponible,
                cantidad_faltante=faltante,
                usuario=request.user,
            )

    # limpia carrito
    request.session["cart"] = {}
    request.session.modified = True

    ticket_url = reverse("ticket_pdf", kwargs={"venta_id": venta.id})
    faltantes_count = venta.faltantes_stock.count()
    if faltantes_count:
        messages.warning(request, f"Venta V{venta.folio} generada con {faltantes_count} producto(s) sin stock suficiente.")
    else:
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
    height = (70 + (len(venta.items.all()) * 14) + 55) * mm

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
    if venta.cliente_fiscal:
        line(f"Cliente: {venta.cliente_fiscal.razon_social[:35]}", size=8, dy=5*mm)
        line(f"RFC: {venta.cliente_fiscal.rfc}", size=8, dy=5*mm)
    line("-"*48, size=9)

    # Items
    for it in venta.items.select_related("producto").all():
        nombre = it.producto.nombre
        line(nombre, size=9, dy=5*mm)
        unidad = "kg" if it.producto.unidad_venta == "KG" else "u"
        line(f"{it.cantidad} {unidad} x ${it.precio_unitario_con_iva} = ${it.subtotal}", size=9, dy=5*mm)
        line(f"Base ${it.base_total} IEPS ${it.ieps_total} IVA ${it.iva_total}", size=7, dy=5*mm)

    line("-"*48, size=9)
    line(f"SUBTOTAL: ${venta.subtotal_base}", size=9, dy=5*mm)
    line(f"IEPS: ${venta.total_ieps}", size=9, dy=5*mm)
    line(f"IVA: ${venta.total_iva}", size=9, dy=5*mm)
    if venta.retencion_isr:
        line(f"RET ISR: -${venta.retencion_isr}", size=9, dy=5*mm)
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
