from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.eanbc import Ean13BarcodeWidget
from reportlab.graphics.barcode.code128 import Code128
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .forms import ProductoAltaForm
from .models import GrupoProducto, SubgrupoProducto, Producto


def user_is_admin(user):
    return user.is_superuser or user.groups.filter(name="Administradores").exists()


def require_admin(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not user_is_admin(request.user):
            return HttpResponseForbidden("No autorizado.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def _ean13_from_id(producto_id):
    base = str(producto_id).zfill(12)
    total = 0
    for idx, ch in enumerate(base):
        n = int(ch)
        total += n if idx % 2 == 0 else n * 3
    check = (10 - (total % 10)) % 10
    return f"{base}{check}"


@require_admin
def producto_alta(request):
    if request.method == "POST":
        form = ProductoAltaForm(request.POST)
        if form.is_valid():
            producto = form.save(commit=False)
            grupo, subgrupo = form.get_or_create_grupos()
            producto.grupo = grupo
            producto.subgrupo = subgrupo
            producto.save()

            generar_barcode = form.cleaned_data.get("generar_barcode")
            if generar_barcode and not producto.barcode:
                producto.barcode = _ean13_from_id(producto.id)
                producto.save(update_fields=["barcode"])

            generar_qr = form.cleaned_data.get("generar_qr")
            qty = form.cleaned_data.get("etiquetas_qty") or 1
            etiquetas_url = None
            if (generar_barcode or generar_qr) and qty > 0:
                params = []
                if generar_barcode:
                    params.append("barcode=1")
                if generar_qr:
                    params.append("qr=1")
                params.append(f"qty={qty}")
                etiquetas_url = reverse("catalog_etiquetas", kwargs={"producto_id": producto.id})
                etiquetas_url = f"{etiquetas_url}?{'&'.join(params)}"

            messages.success(request, "Producto creado.")
            form = ProductoAltaForm()
            return render(
                request,
                "catalog/producto_alta.html",
                {"form": form, "etiquetas_url": etiquetas_url},
            )
    else:
        form = ProductoAltaForm()

    return render(request, "catalog/producto_alta.html", {"form": form})


@require_admin
def producto_editar(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    if request.method == "POST":
        form = ProductoAltaForm(request.POST, instance=producto)
        if form.is_valid():
            producto = form.save(commit=False)
            grupo, subgrupo = form.get_or_create_grupos()
            producto.grupo = grupo
            producto.subgrupo = subgrupo
            producto.save()

            generar_barcode = form.cleaned_data.get("generar_barcode")
            if generar_barcode and not producto.barcode:
                producto.barcode = _ean13_from_id(producto.id)
                producto.save(update_fields=["barcode"])

            generar_qr = form.cleaned_data.get("generar_qr")
            qty = form.cleaned_data.get("etiquetas_qty") or 1
            etiquetas_url = None
            if (generar_barcode or generar_qr) and qty > 0:
                params = []
                if generar_barcode:
                    params.append("barcode=1")
                if generar_qr:
                    params.append("qr=1")
                params.append(f"qty={qty}")
                etiquetas_url = reverse("catalog_etiquetas", kwargs={"producto_id": producto.id})
                etiquetas_url = f"{etiquetas_url}?{'&'.join(params)}"

            messages.success(request, "Producto actualizado.")
            form = ProductoAltaForm(
                instance=producto,
                initial={
                    "grupo_nombre": producto.grupo.nombre if producto.grupo else "",
                    "subgrupo_nombre": producto.subgrupo.nombre if producto.subgrupo else "",
                },
            )
            return render(
                request,
                "catalog/producto_editar.html",
                {"form": form, "producto": producto, "etiquetas_url": etiquetas_url},
            )
    else:
        form = ProductoAltaForm(
            instance=producto,
            initial={
                "grupo_nombre": producto.grupo.nombre if producto.grupo else "",
                "subgrupo_nombre": producto.subgrupo.nombre if producto.subgrupo else "",
            },
        )

    return render(
        request,
        "catalog/producto_editar.html",
        {"form": form, "producto": producto},
    )


@require_admin
def inventario(request):
    q = (request.GET.get("q", "") or "").strip()
    productos_qs = Producto.objects.select_related("grupo", "subgrupo").order_by("nombre")
    if q:
        productos_qs = productos_qs.filter(
            Q(nombre__icontains=q)
            | Q(sku__icontains=q)
            | Q(barcode__icontains=q)
            | Q(grupo__nombre__icontains=q)
            | Q(subgrupo__nombre__icontains=q)
        )

    grupos_data = []
    grupos_map = {}
    productos_sin_grupo = []

    for producto in productos_qs:
        if not producto.grupo:
            productos_sin_grupo.append(producto)
            continue

        grupo_id = producto.grupo_id
        if grupo_id not in grupos_map:
            grupos_map[grupo_id] = {
                "grupo": producto.grupo,
                "subgrupos": {},
                "productos_sin_sub": [],
            }
        grupo_entry = grupos_map[grupo_id]

        if producto.subgrupo:
            sub_id = producto.subgrupo_id
            if sub_id not in grupo_entry["subgrupos"]:
                grupo_entry["subgrupos"][sub_id] = {
                    "subgrupo": producto.subgrupo,
                    "productos": [],
                }
            grupo_entry["subgrupos"][sub_id]["productos"].append(producto)
        else:
            grupo_entry["productos_sin_sub"].append(producto)

    for entry in grupos_map.values():
        subgrupos_data = list(entry["subgrupos"].values())
        subgrupos_data.sort(key=lambda x: x["subgrupo"].nombre)
        grupos_data.append(
            {
                "grupo": entry["grupo"],
                "subgrupos": subgrupos_data,
                "productos_sin_sub": entry["productos_sin_sub"],
            }
        )
    grupos_data.sort(key=lambda x: x["grupo"].nombre)
    return render(
        request,
        "catalog/inventario.html",
        {
            "grupos": grupos_data,
            "productos_sin_grupo": productos_sin_grupo,
            "q": q,
        },
    )


@require_admin
def etiquetas_pdf(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)
    include_barcode = request.GET.get("barcode") == "1"
    include_qr = request.GET.get("qr") == "1"
    qty = int(request.GET.get("qty", "1") or "1")
    qty = max(qty, 1)

    if include_barcode and not producto.barcode:
        producto.barcode = _ean13_from_id(producto.id)
        producto.save(update_fields=["barcode"])

    response = HttpResponse(content_type="application/pdf")
    stamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'inline; filename="etiquetas_{producto.id}_{stamp}.pdf"'

    c = canvas.Canvas(response, pagesize=A4)
    page_w, page_h = A4

    cols = 3
    rows = 8
    label_w = 70 * mm
    label_h = 35 * mm
    margin_x = 5 * mm
    margin_y = 7 * mm

    def draw_label(x, y):
        padding = 2 * mm
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x + padding, y + label_h - 10 * mm, producto.nombre[:30])
        c.setFont("Helvetica", 7)
        c.drawString(x + padding, y + label_h - 16 * mm, f"SKU: {producto.sku or producto.id}")
        c.drawString(x + padding, y + label_h - 22 * mm, f"Precio: ${producto.precio_con_iva}")

        if include_barcode and producto.barcode:
            if producto.barcode.isdigit() and len(producto.barcode) == 13:
                barcode = Ean13BarcodeWidget(producto.barcode)
                barcode.barHeight = 10 * mm
                barcode.barWidth = 0.28 * mm
                d = Drawing(42 * mm, 12 * mm)
                d.add(barcode)
                renderPDF.draw(d, c, x + padding, y + 3 * mm)
            else:
                code128 = Code128(producto.barcode, barHeight=10 * mm, barWidth=0.4)
                code128.drawOn(c, x + padding, y + 3 * mm)
            c.setFont("Helvetica", 6)
            c.drawString(x + padding, y + 1 * mm, producto.barcode)

        if include_qr:
            qr_value = producto.sku or str(producto.id)
            qr = QrCodeWidget(qr_value)
            bounds = qr.getBounds()
            size = 16 * mm
            qd = Drawing(size, size, transform=[size / (bounds[2] - bounds[0]), 0, 0, size / (bounds[3] - bounds[1]), 0, 0])
            qd.add(qr)
            renderPDF.draw(qd, c, x + label_w - 18 * mm, y + label_h - 20 * mm)

    total_per_page = cols * rows
    for idx in range(qty):
        if idx > 0 and idx % total_per_page == 0:
            c.showPage()
        local = idx % total_per_page
        col = local % cols
        row = local // cols
        x = margin_x + (col * label_w)
        y = page_h - margin_y - label_h - (row * label_h)
        draw_label(x, y)

    c.showPage()
    c.save()
    return response
