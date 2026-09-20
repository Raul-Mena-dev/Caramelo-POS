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
from core.models import ConfiguracionNegocio
from sales.models import ClienteFiscal, FolioVenta, Venta, VentaItem, MovimientoInventario, VentaSinStock
from sales.models import CajaTurno

MONEY = Decimal("0.01")

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
        "costo_unitario": producto.costo,
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
        "puede_cancelar": request.user.is_superuser or request.user.groups.filter(name="Administradores").exists(),
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
    if not p.permite_decimales and qty != qty.to_integral_value():
        messages.error(request, f"{p.nombre} solo admite cantidades enteras.")
        return redirect("pos_home")
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
    metodos_validos = {value for value, _label in Venta.METODOS}
    if metodo not in metodos_validos:
        return HttpResponseBadRequest("Metodo de pago invalido")
    cliente_id = request.POST.get("cliente_fiscal_id") or None
    cliente = None
    if cliente_id:
        cliente = get_object_or_404(ClienteFiscal, id=int(cliente_id), activo=True)

    cart = _get_cart(request.session)
    try:
        producto_ids = [int(pid) for pid in cart]
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Carrito invalido")
    productos = {
        producto.id: producto
        for producto in Producto.objects.select_for_update().filter(id__in=producto_ids, activo=True)
    }
    items = []
    total_bruto = Decimal("0.00")
    for pid, qty_str in cart.items():
        producto = productos.get(int(pid))
        cantidad = _decimal(qty_str)
        if not producto or cantidad <= 0:
            continue
        if not producto.permite_decimales and cantidad != cantidad.to_integral_value():
            messages.error(request, f"{producto.nombre} solo admite cantidades enteras.")
            return redirect("pos_home")
        item = _item_snapshot(producto, cantidad)
        items.append(item)
        total_bruto += item["subtotal"]
    total_bruto = total_bruto.quantize(MONEY)
    if not items:
        return HttpResponseBadRequest("Carrito vacío")

    config = ConfiguracionNegocio.cargar()
    faltantes_bloqueados = [
        it for it in items
        if it["producto"].controla_inventario and it["producto"].stock_actual < it["cantidad"]
    ]
    if faltantes_bloqueados and not config.permitir_venta_sin_stock:
        nombres = ", ".join(it["producto"].nombre for it in faltantes_bloqueados[:3])
        messages.error(request, f"Stock insuficiente: {nombres}.")
        return redirect("pos_home")

    subtotal_base = sum((it["base_total"] for it in items), Decimal("0.00")).quantize(MONEY)
    total_ieps = sum((it["ieps_total"] for it in items), Decimal("0.00")).quantize(MONEY)
    total_iva = sum((it["iva_total"] for it in items), Decimal("0.00")).quantize(MONEY)
    retencion_isr = Decimal("0.00")
    if cliente and cliente.tipo_persona == "MORAL" and config.aplicar_retencion_persona_moral:
        tasa_retencion = Decimal(config.retencion_persona_moral) / Decimal("100")
        retencion_isr = (subtotal_base * tasa_retencion).quantize(MONEY)
    total = (total_bruto - retencion_isr).quantize(MONEY)

    efectivo_recibido = Decimal("0.00")
    cambio = Decimal("0.00")
    if metodo == "EFECTIVO":
        efectivo_recibido = _decimal(request.POST.get("efectivo_recibido"), str(total)).quantize(MONEY)
        if efectivo_recibido < total:
            messages.error(request, "El efectivo recibido no alcanza para cubrir el total.")
            return redirect("pos_home")
        cambio = (efectivo_recibido - total).quantize(MONEY)

    folio = FolioVenta.siguiente()

    venta = Venta.objects.create(
        folio=folio,
        metodo_pago=metodo,
        subtotal_base=subtotal_base,
        total_ieps=total_ieps,
        total_iva=total_iva,
        retencion_isr=retencion_isr,
        total=total,
        efectivo_recibido=efectivo_recibido,
        cambio=cambio,
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
            costo_unitario=it["costo_unitario"],
        )

        if not p.controla_inventario:
            continue

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
    es_admin = request.user.is_superuser or request.user.groups.filter(name="Administradores").exists()
    if venta.usuario_id != request.user.id and not es_admin:
        return HttpResponse(status=403)
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
    config = ConfiguracionNegocio.cargar()
    line(config.nombre_comercial, size=14, dy=8*mm)
    if config.rfc:
        line(f"RFC: {config.rfc}", size=8, dy=5*mm)
    if config.domicilio:
        line(config.domicilio, size=8, dy=5*mm)
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
        unidad = it.producto.abreviatura_unidad
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
    if venta.metodo_pago == "EFECTIVO":
        line(f"RECIBIDO: ${venta.efectivo_recibido}", size=9, dy=5*mm)
        line(f"CAMBIO: ${venta.cambio}", size=9, dy=5*mm)
    if venta.estatus == "CANCELADA":
        line("*** VENTA CANCELADA ***", size=10, dy=6*mm)
    line(config.mensaje_ticket, size=10, dy=8*mm)

    c.showPage()
    c.save()
    return response


@login_required
@transaction.atomic
def venta_cancelar(request, venta_id: int):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")
    es_admin = request.user.is_superuser or request.user.groups.filter(name="Administradores").exists()
    if not es_admin:
        return HttpResponse(status=403)

    venta = get_object_or_404(Venta.objects.select_for_update(), id=venta_id)
    if venta.estatus != "ACTIVA":
        messages.info(request, f"La venta V{venta.folio} ya no esta activa.")
        return redirect("pos_home")

    motivo = (request.POST.get("motivo") or "Cancelacion autorizada").strip()[:180]
    productos = {
        producto.id: producto
        for producto in Producto.objects.select_for_update().filter(
            id__in=venta.items.values_list("producto_id", flat=True)
        )
    }
    referencia = f"V{venta.folio}"
    for item in venta.items.all():
        producto = productos[item.producto_id]
        descontado = MovimientoInventario.objects.filter(
            producto_id=producto.id,
            tipo="VENTA",
            referencia=referencia,
        ).aggregate(total=Sum("cantidad"))["total"] or Decimal("0.000")
        reintegro = -descontado
        if reintegro > 0:
            producto.stock_actual += reintegro
            producto.save(update_fields=["stock_actual"])
            MovimientoInventario.objects.create(
                producto=producto,
                tipo="CANCELACION",
                cantidad=reintegro,
                referencia=referencia,
                usuario=request.user,
            )

    venta.estatus = "CANCELADA"
    venta.cancelada_en = timezone.now()
    venta.cancelada_por = request.user
    venta.motivo_cancelacion = motivo
    venta.save(update_fields=["estatus", "cancelada_en", "cancelada_por", "motivo_cancelacion"])
    messages.success(request, f"Venta V{venta.folio} cancelada; el inventario fue restituido.")
    return redirect("pos_home")

def _get_turno_abierto(user):
    return CajaTurno.objects.filter(usuario=user, estatus="ABIERTO").order_by("-apertura").first()

@login_required
def turno_home(request):
    turno = _get_turno_abierto(request.user)
    return render(request, "pos/turno.html", {"turno": turno})

@login_required
@transaction.atomic
def turno_abrir(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    # Evita dos turnos abiertos por usuario
    if _get_turno_abierto(request.user):
        return HttpResponseBadRequest("Ya tienes un turno abierto.")

    caja = (request.POST.get("caja_nombre") or "CAJA1").strip()[:40]
    if CajaTurno.objects.select_for_update().filter(caja_nombre__iexact=caja, estatus="ABIERTO").exists():
        return HttpResponseBadRequest("Esa caja ya tiene un turno abierto.")
    fondo = Decimal((request.POST.get("fondo_inicial") or "0").strip() or "0")

    CajaTurno.objects.create(
        caja_nombre=caja,
        usuario=request.user,
        fondo_inicial=fondo,
        estatus="ABIERTO",
    )
    return redirect("pos_home")

@login_required
@transaction.atomic
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
