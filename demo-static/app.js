const STORAGE_KEY = "pos-comercio-demo-v1";
const SESSION_KEY = "pos-comercio-demo-entered";
const money = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });
const quantity = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 3 });
const dateTime = new Intl.DateTimeFormat("es-MX", { dateStyle: "medium", timeStyle: "short" });

let initialState;
let state;
let currentView = "pos";
let searchTerm = "";

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const safe = (value = "") => String(value).replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
const roundMoney = value => Math.round((Number(value) + Number.EPSILON) * 100) / 100;
const productById = id => state.products.find(product => product.id === Number(id));
const supplierById = id => state.suppliers.find(supplier => supplier.id === Number(id));
const cartTotal = () => roundMoney(state.cart.reduce((sum, line) => sum + productById(line.productId).price * line.quantity, 0));
const nextId = records => records.length ? Math.max(...records.map(record => record.id)) + 1 : 1;

async function boot() {
  const response = await fetch("./data/demo.json", { cache: "no-store" });
  if (!response.ok) throw new Error("No se pudieron cargar los datos de demostración.");
  initialState = await response.json();
  const stored = localStorage.getItem(STORAGE_KEY);
  try { state = stored ? JSON.parse(stored) : structuredClone(initialState); }
  catch { state = structuredClone(initialState); }
  if (!state.products || !state.sales || !state.suppliers) state = structuredClone(initialState);
  save();
  $("#loading").classList.add("hidden");
  if (sessionStorage.getItem(SESSION_KEY)) showApp();
  else $("#welcome").classList.remove("hidden");
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function showApp() {
  sessionStorage.setItem(SESSION_KEY, "1");
  $("#welcome").classList.add("hidden");
  $("#app").classList.remove("hidden");
  navigate(currentView);
}

function navigate(view) {
  currentView = view;
  $$("[data-view]").forEach(button => button.classList.toggle("active", button.dataset.view === view));
  $("#main-nav").classList.remove("open");
  $("#menu-toggle").setAttribute("aria-expanded", "false");
  const views = { pos: renderPos, shift: renderShift, inventory: renderInventory, purchases: renderPurchases, suppliers: renderSuppliers, reports: renderReports };
  (views[view] || renderPos)();
  $("#view").focus({ preventScroll: true });
}

function heading(title, description, actions = "") {
  return `<div class="page-heading"><div><h1>${title}</h1><p>${description}</p></div>${actions ? `<div class="page-actions">${actions}</div>` : ""}</div>`;
}

function renderPos() {
  const normalized = searchTerm.trim().toLowerCase();
  const products = state.products.filter(product => !normalized || `${product.name} ${product.brand} ${product.sku} ${product.barcode}`.toLowerCase().includes(normalized));
  const total = cartTotal();
  const active = state.activeShift;
  $("#view").innerHTML = `
    ${heading("Caja", "Escanea un código o selecciona productos para comenzar una venta.")}
    <div class="grid pos-grid">
      <section class="card">
        <div class="card-header"><h2>Buscar producto</h2><span class="status good">Lector listo</span></div>
        <div class="card-body">
          <div class="scanner"><input id="product-search" value="${safe(searchTerm)}" placeholder="Código de barras, SKU o nombre" autocomplete="off" autofocus><button class="button primary" id="search-button">Buscar</button></div>
          <p class="hint">Prueba el código <code>7501000000015</code> y presiona Enter.</p>
          <div class="product-grid">
            ${products.length ? products.slice(0, 12).map(product => `
              <button class="product-card" data-add-product="${product.id}" ${product.stock <= 0 ? "disabled" : ""}>
                <span><small>${safe(product.category)} · ${safe(product.sku)}</small><strong>${safe(product.name)}</strong><small>${safe(product.brand)}</small></span>
                <span class="product-meta"><span class="${stockClass(product)}">${stockText(product)}</span><strong>${money.format(product.price)}</strong></span>
              </button>`).join("") : `<div class="empty-state full"><h3>Sin coincidencias</h3><p>Intenta con otro nombre o código.</p></div>`}
          </div>
        </div>
      </section>
      <aside class="card">
        <div class="card-header"><h2>Venta actual</h2>${state.cart.length ? `<button class="link-button" id="clear-cart">Vaciar</button>` : ""}</div>
        <div class="card-body">
          <div class="shift-alert ${active ? "" : "closed"}"><span>${active ? `Turno abierto · ${safe(active.register)}` : "Necesitas abrir un turno para cobrar"}</span><button class="link-button" data-view="shift">${active ? "Ver turno" : "Abrir"}</button></div>
          <div id="cart-lines">
            ${state.cart.length ? state.cart.map(line => cartLine(line)).join("") : `<div class="cart-empty"><div><strong>El carrito está vacío</strong><span>Agrega un producto desde el catálogo.</span></div></div>`}
          </div>
          <div class="totals">
            <div class="total-row"><span>Artículos</span><strong>${quantity.format(state.cart.reduce((sum, line) => sum + line.quantity, 0))}</strong></div>
            <div class="total-row grand"><span>Total</span><strong>${money.format(total)}</strong></div>
          </div>
          <div class="checkout-fields">
            <div class="field"><label for="payment-method">Método de pago</label><select id="payment-method"><option value="EFECTIVO">Efectivo</option><option value="TARJETA">Tarjeta</option><option value="TRANSFER">Transferencia</option></select></div>
            <div class="field" id="cash-field"><label for="cash-received">Efectivo recibido</label><input id="cash-received" type="number" min="0" step="0.01" placeholder="0.00"></div>
          </div>
          <button class="button primary checkout-button" id="checkout" ${!active || !state.cart.length ? "disabled" : ""}>Cobrar ${money.format(total)}</button>
        </div>
      </aside>
    </div>`;
  bindPos();
}

function cartLine(line) {
  const product = productById(line.productId);
  return `<div class="cart-line"><div><strong>${safe(product.name)}</strong><small>${money.format(product.price)} / ${safe(product.unit)}</small></div><div class="qty-control"><button data-qty="-1" data-id="${product.id}" aria-label="Restar">&minus;</button><span>${quantity.format(line.quantity)}</span><button data-qty="1" data-id="${product.id}" aria-label="Sumar">+</button></div><strong class="right">${money.format(product.price * line.quantity)}</strong><button class="remove" data-remove="${product.id}" aria-label="Quitar">&times;</button></div>`;
}

function bindPos() {
  const input = $("#product-search");
  input.addEventListener("input", event => { searchTerm = event.target.value; });
  input.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const value = input.value.trim().toLowerCase();
    const exact = state.products.find(product => product.barcode.toLowerCase() === value || product.sku.toLowerCase() === value);
    if (exact) { searchTerm = ""; addProduct(exact.id); }
    else { searchTerm = input.value; renderPos(); }
  });
  $("#search-button").addEventListener("click", () => { searchTerm = input.value; renderPos(); });
  $$('[data-add-product]').forEach(button => button.addEventListener("click", () => addProduct(button.dataset.addProduct)));
  $$('[data-qty]').forEach(button => button.addEventListener("click", () => changeQuantity(button.dataset.id, Number(button.dataset.qty))));
  $$('[data-remove]').forEach(button => button.addEventListener("click", () => { state.cart = state.cart.filter(line => line.productId !== Number(button.dataset.remove)); save(); renderPos(); }));
  $("#clear-cart")?.addEventListener("click", () => { state.cart = []; save(); renderPos(); });
  $("#payment-method").addEventListener("change", event => $("#cash-field").classList.toggle("hidden", event.target.value !== "EFECTIVO"));
  $("#checkout").addEventListener("click", checkout);
  queueMicrotask(() => input.focus());
}

function addProduct(productId) {
  const product = productById(productId);
  const line = state.cart.find(item => item.productId === product.id);
  const current = line?.quantity || 0;
  if (current + 1 > product.stock) return toast("No hay existencia suficiente para agregar otra unidad.");
  if (line) line.quantity += 1;
  else state.cart.push({ productId: product.id, quantity: 1 });
  save();
  toast(`${product.name} agregado`);
  renderPos();
}

function changeQuantity(productId, delta) {
  const line = state.cart.find(item => item.productId === Number(productId));
  const product = productById(productId);
  if (!line) return;
  const next = line.quantity + delta;
  if (next <= 0) state.cart = state.cart.filter(item => item !== line);
  else if (next <= product.stock) line.quantity = next;
  else return toast("No hay existencia suficiente.");
  save(); renderPos();
}

function checkout() {
  if (!state.activeShift) return toast("Abre un turno antes de cobrar.");
  if (!state.cart.length) return;
  const total = cartTotal();
  const method = $("#payment-method").value;
  const received = method === "EFECTIVO" ? Number($("#cash-received").value) : 0;
  if (method === "EFECTIVO" && received < total) return toast("El efectivo recibido no cubre el total.");
  for (const line of state.cart) if (line.quantity > productById(line.productId).stock) return toast("El inventario cambió; revisa las cantidades.");
  const id = nextId(state.sales);
  const sale = {
    id, folio: `V${id}`, date: new Date().toISOString(), method, total,
    received: method === "EFECTIVO" ? roundMoney(received) : 0,
    change: method === "EFECTIVO" ? roundMoney(received - total) : 0,
    items: state.cart.map(line => ({ productId: line.productId, quantity: line.quantity, price: productById(line.productId).price, cost: productById(line.productId).cost }))
  };
  sale.items.forEach(line => { productById(line.productId).stock = roundMoney(productById(line.productId).stock - line.quantity); });
  state.sales.push(sale);
  state.activeShift.saleIds.push(sale.id);
  state.cart = [];
  save();
  renderPos();
  showTicket(sale);
}

function renderShift() {
  const shift = state.activeShift;
  $("#view").innerHTML = `
    ${heading("Turno de caja", "Registra la apertura, controla lo cobrado y realiza el corte.")}
    <section class="card shift-panel"><div class="shift-hero">
      <div class="shift-icon">${shift ? "●" : "○"}</div>
      ${shift ? openShiftTemplate(shift) : closedShiftTemplate()}
    </div></section>`;
  $("#open-shift")?.addEventListener("click", openShift);
  $("#close-shift")?.addEventListener("click", closeShift);
}

function closedShiftTemplate() {
  const last = state.shifts.at(-1);
  return `<h2>No hay turno abierto</h2><p>Inicia una caja para habilitar el cobro.</p>
    ${last ? `<div class="summary-list"><div><span>Último cierre</span><strong>${dateTime.format(new Date(last.closedAt))}</strong></div><div><span>Caja</span><strong>${safe(last.register)}</strong></div></div>` : ""}
    <div class="form-grid"><div class="field"><label for="register">Caja</label><select id="register"><option>CAJA1</option><option>CAJA2</option></select></div><div class="field"><label for="opening-cash">Fondo inicial</label><input id="opening-cash" type="number" value="500" min="0" step="0.01"></div></div>
    <button class="button primary large full" id="open-shift" style="width:100%;margin-top:18px">Abrir turno</button>`;
}

function openShiftTemplate(shift) {
  const sales = state.sales.filter(sale => shift.saleIds.includes(sale.id));
  const total = sales.reduce((sum, sale) => sum + sale.total, 0);
  const cash = sales.filter(sale => sale.method === "EFECTIVO").reduce((sum, sale) => sum + sale.total, 0);
  return `<span class="status good">Turno abierto</span><h2 style="margin-top:14px">${safe(shift.register)}</h2><p>Abierto ${dateTime.format(new Date(shift.openedAt))}</p>
    <div class="summary-list"><div><span>Fondo inicial</span><strong>${money.format(shift.openingCash)}</strong></div><div><span>Ventas</span><strong>${sales.length}</strong></div><div><span>Total vendido</span><strong>${money.format(total)}</strong></div><div><span>Efectivo esperado</span><strong>${money.format(shift.openingCash + cash)}</strong></div></div>
    <div class="field"><label for="counted-cash">Efectivo contado al cierre</label><input id="counted-cash" type="number" min="0" step="0.01" value="${roundMoney(shift.openingCash + cash)}"></div>
    <button class="button danger large" id="close-shift" style="width:100%;margin-top:18px">Cerrar turno y ver corte</button>`;
}

function openShift() {
  state.activeShift = { id: nextId(state.shifts), register: $("#register").value, openedAt: new Date().toISOString(), openingCash: Number($("#opening-cash").value) || 0, status: "ABIERTO", saleIds: [] };
  save(); toast("Turno abierto correctamente."); navigate("pos");
}

function closeShift() {
  const shift = state.activeShift;
  const counted = Number($("#counted-cash").value);
  if (!Number.isFinite(counted) || counted < 0) return toast("Captura el efectivo contado.");
  const sales = state.sales.filter(sale => shift.saleIds.includes(sale.id));
  const cash = sales.filter(sale => sale.method === "EFECTIVO").reduce((sum, sale) => sum + sale.total, 0);
  state.shifts.push({ ...shift, closedAt: new Date().toISOString(), countedCash: counted, status: "CERRADO", difference: roundMoney(counted - shift.openingCash - cash) });
  state.activeShift = null;
  save(); toast("Turno cerrado. El corte está listo."); navigate("reports");
}

function renderInventory(filter = "") {
  const term = filter.toLowerCase();
  const rows = state.products.filter(product => `${product.name} ${product.sku} ${product.barcode}`.toLowerCase().includes(term));
  const units = state.products.reduce((sum, product) => sum + product.stock, 0);
  const costValue = state.products.reduce((sum, product) => sum + product.stock * product.cost, 0);
  const low = state.products.filter(product => product.stock <= product.minimum).length;
  $("#view").innerHTML = `${heading("Inventario", "Consulta existencias, códigos y valor actual del catálogo.", `<button class="button secondary" data-view="purchases">Registrar compra</button>`)}
    <div class="stats"><article class="card stat"><span>Productos</span><strong>${state.products.length}</strong></article><article class="card stat"><span>Unidades</span><strong>${quantity.format(units)}</strong></article><article class="card stat"><span>Stock bajo</span><strong>${low}</strong></article><article class="card stat"><span>Valor a costo</span><strong>${money.format(costValue)}</strong></article></div>
    <section class="card"><div class="card-header"><h2>Existencias</h2><div class="scanner"><input id="inventory-search" value="${safe(filter)}" placeholder="Buscar o escanear"></div></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Producto</th><th>Código</th><th>Categoría</th><th class="right">Costo</th><th class="right">Precio</th><th class="right">Existencia</th><th>Estado</th></tr></thead><tbody>${rows.map(product => `<tr><td><strong>${safe(product.name)}</strong><br><small class="muted">${safe(product.sku)} · ${safe(product.brand)}</small></td><td>${safe(product.barcode)}</td><td>${safe(product.category)}</td><td class="right">${money.format(product.cost)}</td><td class="right">${money.format(product.price)}</td><td class="right"><strong>${quantity.format(product.stock)} ${safe(product.unit)}</strong></td><td><span class="${stockClass(product)}">${stockText(product)}</span></td></tr>`).join("")}</tbody></table></div></section>`;
  $("#inventory-search").addEventListener("input", event => renderInventory(event.target.value));
  $("#inventory-search").focus();
}

function stockClass(product) { return `status ${product.stock <= 0 ? "bad" : product.stock <= product.minimum ? "warn" : "good"}`; }
function stockText(product) { return product.stock <= 0 ? "Sin stock" : product.stock <= product.minimum ? "Stock bajo" : "Disponible"; }

function renderPurchases() {
  $("#view").innerHTML = `${heading("Compras", "Recibe mercancía y actualiza existencias y costos.")}
    <div class="split"><section class="card"><div class="card-header"><h2>Nueva recepción</h2></div><div class="card-body"><div class="stack">
      <div class="field"><label for="purchase-supplier">Proveedor</label><select id="purchase-supplier">${state.suppliers.map(supplier => `<option value="${supplier.id}">${safe(supplier.name)}</option>`).join("")}</select></div>
      <div class="field"><label for="purchase-product">Producto</label><select id="purchase-product">${state.products.map(product => `<option value="${product.id}">${safe(product.name)} · ${quantity.format(product.stock)} ${safe(product.unit)}</option>`).join("")}</select></div>
      <div class="form-grid"><div class="field"><label for="purchase-qty">Cantidad recibida</label><input id="purchase-qty" type="number" min="0.001" step="0.001" value="12"></div><div class="field"><label for="purchase-cost">Costo unitario</label><input id="purchase-cost" type="number" min="0" step="0.01" value="18.50"></div></div>
      <div class="field"><label for="purchase-document">Documento</label><input id="purchase-document" placeholder="Factura o remisión"></div>
      <button class="button primary large" id="save-purchase">Recibir compra</button>
    </div></div></section>
    <section class="card"><div class="card-header"><h2>Historial</h2><span class="status good">${state.purchases.length} compras</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Folio</th><th>Fecha</th><th>Proveedor</th><th>Documento</th><th class="right">Total</th></tr></thead><tbody>${[...state.purchases].reverse().map(purchase => `<tr><td><strong>${safe(purchase.folio)}</strong></td><td>${dateTime.format(new Date(purchase.date))}</td><td>${safe(supplierById(purchase.supplierId)?.name)}</td><td>${safe(purchase.document || "Sin documento")}</td><td class="right"><strong>${money.format(purchase.total)}</strong></td></tr>`).join("")}</tbody></table></div></section></div>`;
  $("#purchase-product").addEventListener("change", event => { $("#purchase-cost").value = productById(event.target.value).cost.toFixed(2); });
  $("#save-purchase").addEventListener("click", savePurchase);
}

function savePurchase() {
  const product = productById($("#purchase-product").value);
  const qty = Number($("#purchase-qty").value);
  const cost = Number($("#purchase-cost").value);
  if (!(qty > 0) || !(cost >= 0)) return toast("Revisa la cantidad y el costo.");
  const id = nextId(state.purchases);
  const previousUnits = product.stock;
  product.cost = roundMoney(((previousUnits * product.cost) + (qty * cost)) / (previousUnits + qty));
  product.stock = roundMoney(previousUnits + qty);
  state.purchases.push({ id, folio: `C${id}`, date: new Date().toISOString(), supplierId: Number($("#purchase-supplier").value), document: $("#purchase-document").value.trim(), total: roundMoney(qty * cost), items: [{ productId: product.id, quantity: qty, unitCost: cost }] });
  save(); toast(`Compra C${id} recibida; inventario actualizado.`); renderPurchases();
}

function renderSuppliers() {
  $("#view").innerHTML = `${heading("Proveedores", "Contactos y condiciones para reabastecer el negocio.", `<button class="button primary" data-view="purchases">Nueva compra</button>`)}
    <div class="supplier-grid">${state.suppliers.map(supplier => { const purchases = state.purchases.filter(purchase => purchase.supplierId === supplier.id); const total = purchases.reduce((sum, purchase) => sum + purchase.total, 0); return `<article class="card supplier-card"><span class="status good">Activo</span><h3>${safe(supplier.name)}</h3><p>${safe(supplier.contact)}</p><p>${safe(supplier.phone)} · ${safe(supplier.email)}</p><p>${safe(supplier.notes)}</p><div class="summary-list"><div><span>Compras</span><strong>${purchases.length}</strong></div><div><span>Total recibido</span><strong>${money.format(total)}</strong></div></div></article>`; }).join("")}</div>`;
}

function renderReports() {
  const sales = state.sales;
  const revenue = sales.reduce((sum, sale) => sum + sale.total, 0);
  const cost = sales.reduce((sum, sale) => sum + sale.items.reduce((lineSum, line) => lineSum + line.cost * line.quantity, 0), 0);
  const profit = revenue - cost;
  const byProduct = new Map();
  sales.forEach(sale => sale.items.forEach(line => {
    const existing = byProduct.get(line.productId) || { quantity: 0, revenue: 0, cost: 0 };
    existing.quantity += line.quantity; existing.revenue += line.price * line.quantity; existing.cost += line.cost * line.quantity; byProduct.set(line.productId, existing);
  }));
  $("#view").innerHTML = `${heading("Cortes y utilidad", "Resumen acumulado de las operaciones guardadas en esta demostración.")}
    <div class="stats"><article class="card stat"><span>Ventas</span><strong>${sales.length}</strong></article><article class="card stat"><span>Ingresos</span><strong>${money.format(revenue)}</strong></article><article class="card stat"><span>Costo vendido</span><strong>${money.format(cost)}</strong></article><article class="card stat"><span>Utilidad bruta</span><strong>${money.format(profit)}</strong></article></div>
    <section class="card"><div class="card-header"><h2>Desempeño por producto</h2><span class="status good">Margen ${revenue ? Math.round(profit / revenue * 100) : 0}%</span></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Producto</th><th class="right">Cantidad</th><th class="right">Venta</th><th class="right">Costo</th><th class="right">Utilidad</th></tr></thead><tbody>${[...byProduct.entries()].sort((a,b) => b[1].revenue - a[1].revenue).map(([id, values]) => `<tr><td><strong>${safe(productById(id)?.name || "Producto")}</strong></td><td class="right">${quantity.format(values.quantity)}</td><td class="right">${money.format(values.revenue)}</td><td class="right">${money.format(values.cost)}</td><td class="right"><strong>${money.format(values.revenue - values.cost)}</strong></td></tr>`).join("")}</tbody></table></div></section>
    <section class="card" style="margin-top:20px"><div class="card-header"><h2>Turnos cerrados</h2></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Caja</th><th>Apertura</th><th>Cierre</th><th class="right">Fondo</th><th class="right">Contado</th><th class="right">Diferencia</th></tr></thead><tbody>${[...state.shifts].reverse().map(shift => `<tr><td><strong>${safe(shift.register)}</strong></td><td>${dateTime.format(new Date(shift.openedAt))}</td><td>${dateTime.format(new Date(shift.closedAt))}</td><td class="right">${money.format(shift.openingCash)}</td><td class="right">${money.format(shift.countedCash)}</td><td class="right">${money.format(shift.difference || 0)}</td></tr>`).join("")}</tbody></table></div></section>`;
}

function showTicket(sale) {
  const root = $("#modal-root");
  root.innerHTML = `<div class="modal-backdrop"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="ticket-title"><div class="modal-header"><h2 id="ticket-title">Venta completada</h2><button class="modal-close" aria-label="Cerrar">&times;</button></div><div class="ticket"><div class="ticket-head"><h3>${safe(state.business.name)}</h3><span>Ticket ${safe(sale.folio)}<br>${dateTime.format(new Date(sale.date))}</span></div><div class="ticket-rule"></div>${sale.items.map(line => `<div><strong>${safe(productById(line.productId).name)}</strong><div class="ticket-line"><span>${quantity.format(line.quantity)} × ${money.format(line.price)}</span><span>${money.format(line.quantity * line.price)}</span></div></div>`).join("")}<div class="ticket-rule"></div><div class="ticket-line ticket-total"><span>Total</span><span>${money.format(sale.total)}</span></div><div class="ticket-line"><span>${safe(sale.method)}</span><span>${sale.method === "EFECTIVO" ? `Cambio ${money.format(sale.change)}` : "Pagado"}</span></div><div class="ticket-rule"></div><div class="ticket-head">Gracias por su compra</div></div><div class="modal-actions"><button class="button secondary" id="print-ticket">Imprimir</button><button class="button primary modal-close">Nueva venta</button></div></section></div>`;
  $$(".modal-close", root).forEach(button => button.addEventListener("click", () => root.innerHTML = ""));
  $("#print-ticket").addEventListener("click", () => window.print());
}

function toast(message) {
  const element = $("#toast");
  element.textContent = message; element.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => element.classList.remove("show"), 2600);
}

document.addEventListener("click", event => {
  const navigation = event.target.closest("[data-view]");
  if (navigation) navigate(navigation.dataset.view);
});
$("#enter-demo").addEventListener("click", showApp);
$("#menu-toggle").addEventListener("click", () => {
  const nav = $("#main-nav"); nav.classList.toggle("open"); $("#menu-toggle").setAttribute("aria-expanded", String(nav.classList.contains("open")));
});
$("#reset-demo").addEventListener("click", () => {
  if (!confirm("¿Restablecer productos, ventas, compras y turnos de la demostración?")) return;
  state = structuredClone(initialState); save(); searchTerm = ""; toast("Datos restablecidos."); navigate("pos");
});

boot().catch(error => {
  $("#loading").innerHTML = `<div class="loader-mark">!</div><strong>No pudimos iniciar la demo</strong><p>${safe(error.message)}</p>`;
});
