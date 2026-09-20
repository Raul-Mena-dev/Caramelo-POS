# POS Comercio

Punto de venta Django configurable para tiendas de abarrotes y otros comercios. Incluye catálogo, venta por código de barras, productos por pieza o a granel, inventario, proveedores, compras multiproducto, turnos, tickets y cortes con utilidad.

## Puesta en marcha local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:POS_USE_SQLITE = "1"
python caramelo\manage.py migrate
python caramelo\manage.py createsuperuser
python caramelo\manage.py runserver
```

Abre `http://127.0.0.1:8000/accounts/login/`. Después entra en **Configuración** para capturar nombre, datos, colores, impuestos, redondeo y política de existencias del negocio.

## Configuración

Las variables disponibles están documentadas en `.env.example`. En producción es obligatorio proporcionar una clave segura, desactivar `POS_DEBUG` y configurar los hosts permitidos y las credenciales de PostgreSQL.

Las reglas comerciales editables desde Django Admin incluyen:

- Identidad y datos para tickets y reportes.
- IVA, IEPS y margen inicial para nuevos productos.
- Redondeo a centavos, $0.10, $0.50 o $1.00.
- Bloqueo o autorización de ventas sin stock.
- Aplicación opcional y tasa de retención para persona moral.

## Verificación

```powershell
$env:POS_USE_SQLITE = "1"
python caramelo\manage.py check
python caramelo\manage.py makemigrations --check --dry-run
python caramelo\manage.py test catalog pos reports
```

## Notas de operación

- El efectivo recibido y el cambio quedan guardados en la venta.
- Los productos por peso o volumen aceptan cantidades decimales; piezas, paquetes y cajas requieren enteros.
- Una compra puede capturarse directamente en unidades o como presentaciones por factor, por ejemplo `3 cajas × 24 piezas`.
- Solo administradores pueden cancelar una venta. La cancelación registra el motivo y restituye el inventario realmente descontado.
- El costo unitario queda congelado en cada partida de venta para futuros reportes de utilidad.

## Proveedores, compras y utilidad

- **Compras** permite registrar proveedor, documento y varias partidas en una sola recepción.
- Cada partida acepta presentaciones y factor de conversión, por ejemplo `3 cajas × 24 piezas`.
- Al recibir la compra se actualizan existencias, último costo, costo promedio ponderado, precio calculado y movimientos de inventario en una transacción.
- **Cortes** muestra costo de lo vendido, utilidad bruta estimada y margen por rango y producto.
- **Inventario → Valorización** muestra el valor actual a costo, a precio de venta y la utilidad potencial; también se exporta a CSV.

Las ventas realizadas antes de guardar costos históricos se estiman durante la migración usando el costo actual del producto. Las ventas posteriores conservan el costo real que tenía el producto al cobrarse.

## Demo separada para Vercel

El proyecto conserva dos perfiles sin duplicar el código:

- `caramelo.settings`: instalación normal, usada localmente y por el negocio.
- `caramelo.settings_demo`: demostración pública con portada, acceso de un clic, aviso permanente y datos ficticios restablecibles.

En Vercel se selecciona automáticamente el perfil demo. La base debe ser PostgreSQL externa porque el sistema de archivos de las funciones no conserva una base SQLite. Para desplegar:

1. Importa este repositorio en Vercel y conecta una base PostgreSQL (por ejemplo, Neon desde Marketplace).
2. Define `DATABASE_URL` y `POS_SECRET_KEY` en los tres ambientes de Vercel.
3. Opcionalmente cambia `POS_DEMO_USERNAME` y `POS_DEMO_PASSWORD`; los valores predeterminados son `demo` y `DemoPOS2026!`.
4. Despliega. El script de compilación ejecuta migraciones, crea el catálogo ficticio y recopila los estáticos.

Para revisar ese mismo perfil localmente sin afectar la base normal (usa automáticamente `caramelo/db_demo.sqlite3`):

```powershell
python caramelo\manage.py migrate --settings=caramelo.settings_demo
python caramelo\manage.py seed_demo --settings=caramelo.settings_demo
python caramelo\manage.py runserver --settings=caramelo.settings_demo
```

La demo abre en `http://127.0.0.1:8000/`. El comando `seed_demo --reset` borra y reconstruye solo los datos comerciales de la base conectada, y se niega a ejecutarse con la configuración normal.
