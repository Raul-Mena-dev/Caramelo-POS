# Manual de Usuario - POS Comercio

Guía de operación para tiendas y comercios: caja, productos, inventario, compras, reportes y uso con lector de códigos.

## 1. Acceso al Sistema

1. Abra la página del sistema en el navegador.
2. Ingrese usuario y contraseña.
3. Después de iniciar sesión, entre a **Caja** para vender.

Si no recuerda la contraseña, el administrador debe cambiarla desde la herramienta administrativa del sistema.

## 2. Menú Principal

| Opción | Uso |
| --- | --- |
| **Caja** | Realizar ventas, escanear productos, cobrar e imprimir ticket. |
| **Turno** | Abrir y cerrar caja con fondo inicial y efectivo contado. |
| **Cortes** | Consultar ventas por fecha, imprimir PDF y descargar CSV. |
| **Inventario** | Administrar productos, compras, ajustes, stock bajo y códigos de barras. |

## 3. Apertura de Turno

Antes de vender es recomendable abrir turno.

1. Entre a **Turno**.
2. Capture el nombre de la caja, por ejemplo `CAJA1`.
3. Capture el fondo inicial en efectivo.
4. Presione **Abrir turno**.

Si no hay turno abierto, el sistema no permitirá cobrar ventas.

## 4. Venta en Caja

### Venta con pistola de códigos

1. Entre a **Caja**.
2. Coloque el cursor en **Escanea o busca producto**.
3. Escanee el código de barras con la pistola.
4. Si el producto existe, se agrega automáticamente al carrito.
5. Seleccione el método de pago.
6. Presione **Cobrar & Ticket**.

### Producto no encontrado

Si el código escaneado no existe, la caja muestra una alerta con **Alta rápida**.

1. Presione **Alta rápida**.
2. El código aparecerá precargado.
3. Capture nombre, costo total, unidades compradas, margen o precio de venta.
4. Guarde el producto y regrese a caja.

### Productos por kilo

Use cantidades decimales:

- `0.250` para 250 gramos.
- `0.500` para medio kilo.
- `1.000` para un kilo.

## 5. Alta de Productos

Campos principales:

| Campo | Qué significa |
| --- | --- |
| **Nombre** | Nombre comercial visible para el cajero. |
| **Código de barras** | Código que lee la pistola. |
| **Costo total compra** | Lo que se pagó por toda la caja, bolsa o paquete. |
| **Unidades compradas** | Cantidad de unidades base recibidas. Sirve para calcular costo unitario. |
| **Stock inicial** | Cantidad disponible para vender. Si queda vacío, usa las unidades compradas. |
| **Stock mínimo** | Nivel de alerta para resurtir. |
| **Margen %** | Ganancia deseada sobre el costo unitario. |
| **Precio venta opcional** | Precio final al público. Si se captura, se respeta; si queda vacío, se calcula. |
| **Unidad venta** | Pieza o kilogramo. |
| **Grupo** | Categoría del producto. |

El sistema muestra **Costo unitario** y **Precio sugerido** mientras captura.

## 6. Cálculo de Precio

El sistema está pensado para venta al público general:

- IVA e IEPS predeterminados: configurables desde la administración del negocio.
- Cada producto puede sobrescribir los porcentajes de impuestos.
- Margen predeterminado: configurable por el administrador.
- Redondeo comercial: configurable desde centavos hasta múltiplos de $1.00.

Si captura precio de venta manual, el sistema lo usa como precio fijo.

## 7. Inventario

Filtros disponibles:

- **Stock bajo:** productos que llegaron al mínimo definido.
- **Sin stock:** productos con existencia en cero o menor.
- **Sin código:** productos pendientes de código de barras.
- **No contables:** productos que se venden, pero no aparecen en reportes contables.

### Ajuste de inventario

Use **Ajuste** para conteo físico, merma, caducidad o corrección.

- Cantidad positiva suma stock.
- Cantidad negativa resta stock.
- Capture motivo: `MERMA`, `CADUCIDAD`, `CONTEO`, etc.

### Proveedores y compras

1. Registre el proveedor desde **Compras → Proveedores**.
2. Abra **Nueva compra** y capture factura, nota u otra referencia.
3. Agregue una o varias partidas indicando presentaciones, unidades por presentación y costo total.
4. Al recibir la compra, el sistema suma inventario, calcula el costo promedio ponderado, recalcula precios y conserva el historial completo.

Ejemplo: `3` cajas con factor `24` agregan `72` piezas al inventario.

### Ventas sin stock suficiente

Por defecto el sistema bloquea una venta cuando no hay existencia suficiente. El administrador puede habilitar la venta con faltantes desde Configuración.

- El inventario nunca baja de 0.
- Si se vende más de lo disponible, el faltante se registra automáticamente.
- El reporte está en **Cortes → Ventas sin stock**.
- Use ese reporte para resurtir o corregir inventario.

## 8. Borrar Productos

En inventario y edición existe la opción **Borrar**.

- Si el producto no tiene historial, se elimina.
- Si ya tiene ventas o movimientos, se desactiva para conservar historial.

Por control fiscal y operativo, no se borra historial de productos ya vendidos.

## 9. Clientes Fiscales

La mayoría de ventas pueden hacerse a **Público general**.

Si un cliente requiere datos fiscales, se puede seleccionar en caja. La retención para persona moral solo se aplica cuando el administrador habilita esa política fiscal.

## 10. Corte de Caja y Reportes

### Cierre de turno

1. Entre a **Turno**.
2. Capture efectivo contado.
3. Presione **Cerrar turno**.
4. Revise total vendido, efectivo esperado y diferencia.

### Corte por rango

1. Entre a **Cortes**.
2. Seleccione fecha de inicio y fecha final.
3. Presione **Aplicar**.
4. Puede imprimir PDF o descargar CSV.

El corte muestra costo de lo vendido, utilidad bruta estimada, margen y utilidad por producto. Use **Inventario → Valorización** para consultar valor a costo, valor a venta y utilidad potencial del stock.

## 11. Recomendaciones Operativas

- Abrir turno antes de empezar a vender.
- Usar la pistola para evitar errores de captura.
- Dar de alta productos con costo total y unidades compradas.
- Revisar **Stock bajo** al iniciar o terminar el día.
- Usar ajustes con motivo cuando haya merma o diferencias de conteo.
- Cerrar turno al final del día o cambio de cajero.

## 12. Problemas Frecuentes

| Situación | Qué hacer |
| --- | --- |
| El código escaneado no aparece. | Use **Alta rápida** para crear el producto. |
| No deja cobrar. | Verifique que haya turno abierto y carrito con productos. |
| No hay stock suficiente. | Por defecto la venta se bloquea. El administrador puede permitirla; en ese caso el faltante aparece en **Ventas sin stock**. |
| El precio sugerido no es el deseado. | Capture **Precio venta opcional** para fijarlo. |
| Un producto ya no debe venderse. | Use **Borrar**; si tiene historial, quedará desactivado. |
