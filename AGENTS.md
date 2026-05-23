# Guia para agentes IA - Caramelo POS

Este repositorio contiene un punto de venta Django para Caramelo. El objetivo principal es vender productos, descontar inventario, emitir tickets PDF, manejar turnos de caja y consultar cortes.

## Resumen rapido

- Stack: Django 5.2.x, PostgreSQL, Bootstrap 5 en templates, ReportLab para PDFs y Waitress como servidor alternativo.
- Raiz del proyecto Django: `caramelo/`.
- Configuracion principal: `caramelo/caramelo/settings.py`.
- URL base de la app operativa: `/pos/`.
- Idioma/zona horaria esperados: `es-mx`, `America/Mexico_City`.
- Autenticacion: Django auth. Login en `/accounts/login/`, logout por POST.

## Estructura relevante

- `caramelo/manage.py`: CLI de Django.
- `caramelo/caramelo/`: settings, urls, wsgi/asgi y `querys.sql`.
- `caramelo/templates/`: templates globales, incluyendo `base.html` y login.
- `caramelo/img/caramelo.png`: logo usado como static asset.
- `caramelo/catalog/`: productos, grupos/subgrupos, inventario, alta/edicion y etiquetas PDF.
- `caramelo/sales/`: modelos de clientes fiscales, venta, items, movimientos de inventario y turnos de caja.
- `caramelo/pos/`: flujo de caja, carrito en sesion, checkout, tickets y apertura/cierre de turnos.
- `caramelo/reports/`: cortes diarios/por rango y cortes por turno, HTML y PDF.

## Setup local esperado

Actualmente no hay `requirements.txt`, `pyproject.toml` ni archivo `.env` en el repo. Para trabajar localmente, un agente debe asumir que hacen falta al menos estas dependencias:

- `Django`
- `psycopg` o `psycopg2-binary` para PostgreSQL
- `reportlab`
- `waitress` si se usa `run_waitress.py`

Base de datos PostgreSQL configurada por defecto en `settings.py`:

```text
ENGINE: django.db.backends.postgresql
NAME: caramelo_db
USER: caramelo_user
PASSWORD: 123456
HOST: 127.0.0.1
PORT: 5433
```

Estas credenciales estan hardcodeadas y `DEBUG=True`; no tratar este proyecto como listo para produccion sin mover secretos a variables de entorno.

Para ejecutar localmente sin PostgreSQL, se puede activar SQLite con:

```bash
export CARAMELO_USE_SQLITE=1
```

Con esa variable, Django usa `caramelo/db.sqlite3`.

## Comandos utiles

Ejecutar desde la raiz del repo:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install Django reportlab waitress psycopg2-binary
python3 caramelo/manage.py migrate
python3 caramelo/manage.py createsuperuser
python3 caramelo/manage.py runserver
```

Si no tienes PostgreSQL levantado en `127.0.0.1:5433`, usa SQLite para desarrollo:

```bash
export CARAMELO_USE_SQLITE=1
python3 caramelo/manage.py migrate
python3 caramelo/manage.py runserver
```

Comandos de verificacion:

```bash
python3 caramelo/manage.py check
python3 caramelo/manage.py test
python3 caramelo/manage.py makemigrations --check --dry-run
```

Servidor Waitress:

```bash
python3 caramelo/run_waitress.py
```

Nota: en el entorno revisado, `python3 caramelo/manage.py check` falla porque Django no esta instalado.

## Dominio y flujo de datos

Catalogo:

- `GrupoProducto` agrupa productos.
- `SubgrupoProducto` pertenece a un grupo y tiene unicidad por `(grupo, nombre)`.
- `Producto` tiene nombre, SKU, barcode unico opcional, precio final, costo/compra, impuestos, margen, unidad de venta, stock, activo, grupo y subgrupo.
- `Producto.calcular_precio()` calcula costo unitario, precio sin impuestos, IEPS, IVA y precio final.
- El precio final se redondea siempre hacia arriba al multiplo de `$0.50`, salvo que `usar_precio_mandatorio` este activo.
- `unidad_venta` puede ser `PIEZA` o `KG`; para `KG`, el POS acepta cantidades decimales en kilogramos.
- `stock_minimo` permite detectar productos de bajo inventario en la vista de inventario.
- `no_contabilizable` permite vender el producto, pero lo excluye de cortes contables y CSV.
- Altas/ediciones usan `ProductoAltaForm`, que puede crear grupo/subgrupo por nombre.
- `ProductoRapidoForm` permite alta rapida desde mostrador, pensado para codigos escaneados no encontrados.
- La captura comercial recomendada es: codigo, nombre, costo total de compra, piezas compradas, margen y opcionalmente precio de venta.
- Si el precio de venta se deja vacio, el sistema calcula precio final con IVA 16%, IEPS 8% y margen por defecto 35%.
- Si el precio de venta se captura, se guarda como precio mandatorio para respetar el precio indicado por el negocio.
- `EntradaCompraForm` registra una entrada simple de compra, suma stock, recalcula precios y crea `MovimientoInventario` tipo `ENTRADA`.
- `AjusteInventarioForm` permite sumar/restar stock por conteo, merma o correccion.
- El borrado de producto es seguro: si no tiene historial se elimina; si tiene ventas/movimientos, se desactiva para conservar trazabilidad.
- Solo superusuarios o usuarios en el grupo `Administradores` pueden acceder a las vistas protegidas por `require_admin`.

Venta/POS:

- El carrito vive en `request.session["cart"]` como `{producto_id: "cantidad"}`.
- `/pos/?q=...` busca producto; si el query coincide exacto con `barcode` o `sku`, agrega 1 unidad automaticamente.
- Si `/pos/?q=...` no encuentra resultados, muestra enlace de alta rapida con el codigo precargado.
- `/pos/clear/` vacia el carrito por POST.
- Checkout requiere un `CajaTurno` abierto del usuario.
- Checkout puede recibir `cliente_fiscal_id`; si el cliente es persona moral, aplica retencion de `1.25%` sobre base.
- `Venta` se crea con folio secuencial `max(folio)+1`.
- `Venta` guarda snapshots: subtotal base, IEPS, IVA, retencion ISR y total final.
- Cada `VentaItem` guarda snapshots fiscales unitarios y totales: base, IEPS, IVA, precio final y subtotal.
- Cada `VentaItem` descuenta `Producto.stock_actual`, incluyendo cantidades decimales para productos por kg.
- Si no hay stock suficiente, la venta se permite, el stock queda en `0` y se registra `VentaSinStock` con el faltante.
- Cada descuento genera un `MovimientoInventario` tipo `VENTA`.
- Al terminar, el carrito se limpia y se redirige a `/pos/?ticket=...` para abrir el ticket PDF.
- `ClienteFiscal` vive en `sales.models` y se administra desde Django admin.

Turnos:

- `CajaTurno` puede estar `ABIERTO` o `CERRADO`.
- Solo se evita doble turno abierto por usuario, no por caja global.
- Al cerrar turno se calculan snapshots: total ventas, efectivo, tarjeta, transferencia y diferencia de efectivo.
- El cierre redirige al corte de turno.

Reportes:

- `reports.views._get_range()` usa query params `start` y `end` en formato `YYYY-MM-DD`; si faltan, usa el dia local actual.
- `corte_diario` realmente funciona como corte por rango.
- El corte diario/rango es contable: filtra ventas activas y excluye items de productos `no_contabilizable`.
- El corte por turno sigue reflejando el dinero real cobrado en caja.
- Hay exportacion CSV para corte diario/rango con desglose por item.
- PDFs se generan con ReportLab directamente desde las vistas.

## Rutas principales

- `/admin/`: admin Django.
- `/accounts/login/`: login.
- `/pos/`: caja.
- `/pos/add/`: agrega/resta items, POST.
- `/pos/checkout/`: cobra, POST.
- `/pos/ticket/<venta_id>.pdf`: ticket PDF.
- `/pos/turno/`: pantalla de turno.
- `/pos/turno/abrir/`: abre turno, POST.
- `/pos/turno/cerrar/`: cierra turno, POST.
- `/catalog/inventario/`: inventario, admin requerido.
- `/catalog/inventario/?filtro=stock_bajo|sin_stock|sin_codigo|no_contable`: filtros operativos de inventario.
- `/catalog/inventario/ajuste/`: ajuste manual de stock, admin requerido.
- `/catalog/compras/nueva/`: entrada simple de compra, admin requerido.
- `/catalog/productos/rapido/`: alta rapida de producto, admin requerido.
- `/catalog/productos/<producto_id>/borrar/`: confirmacion de borrado/desactivacion, admin requerido.
- `/catalog/productos/nuevo/`: alta de producto, admin requerido.
- `/catalog/productos/<producto_id>/editar/`: edicion, admin requerido.
- `/catalog/productos/<producto_id>/etiquetas.pdf`: etiquetas PDF, admin requerido.
- `/reports/diario/`: corte por rango.
- `/reports/diario.pdf`: corte por rango en PDF.
- `/reports/diario.csv`: corte por rango en CSV.
- `/reports/sin-stock/`: reporte de ventas cobradas con faltante de inventario.
- `/reports/sin-stock.csv`: CSV de ventas con faltante de inventario.
- `/reports/turno/<turno_id>/`: corte por turno.
- `/reports/turno/<turno_id>.pdf`: corte por turno en PDF.

## Convenciones al modificar

- Mantener vistas basadas en funciones; el proyecto no usa class-based views.
- Mantener templates Django con Bootstrap 5 y extender `base.html`.
- Usar `Decimal` para dinero/cantidades; evitar `float`.
- Para impuestos y precios, reutilizar `Producto.calcular_precio()` y `Producto.desglose_unitario()`.
- Usar transacciones para cambios que afecten ventas, inventario o caja.
- Si se agregan modelos, crear migraciones en la app correspondiente.
- Si se agregan nuevas pantallas, registrar rutas en el `urls.py` de la app y enlazar desde `base.html` solo si forma parte de navegacion principal.
- Si se agregan permisos de administracion, reutilizar `require_admin` o extraerlo a un helper compartido antes de duplicarlo.

## Riesgos conocidos y mejoras recomendadas

- Falta archivo de dependencias reproducible (`requirements.txt` o `pyproject.toml`).
- `SECRET_KEY`, credenciales DB y `DEBUG=True` estan en `settings.py`.
- `ALLOWED_HOSTS` esta vacio.
- `STATICFILES_DIRS` apunta directo a `BASE_DIR / "img"`; revisar si se desea una estructura static convencional.
- Hay dos scripts de Bootstrap JS en `base.html` con versiones distintas (`5.3.8` y `5.3.3`).
- Folio de venta con `max(folio)+1` puede duplicarse con checkouts concurrentes.
- Checkout descuenta stock sin validar existencia suficiente.
- Cierre de turno no esta envuelto en `transaction.atomic`.
- Admin de `sales` no registra `CajaTurno`.
- `reports/views.py` tiene imports duplicados/no usados.
- Tests actuales estan vacios.

## Primeras pruebas sugeridas para futuros cambios

- Alta de producto con grupo/subgrupo nuevo y generacion de barcode.
- Busqueda por nombre en POS.
- Escaneo por barcode/SKU y auto-agregado al carrito.
- Checkout con turno abierto: crea venta, items, movimiento y descuenta stock.
- Checkout sin turno abierto: bloquea venta.
- Cierre de turno: calcula totales por metodo y diferencia.
- Corte diario con rango invertido: debe intercambiar fechas.
- Generacion de ticket PDF y etiquetas PDF.
