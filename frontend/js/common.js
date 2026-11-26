// ShopEase: code shared by every page (API calls, cart, header, footer).
const API = "/api";
const CART_KEY = "shopease_cart";

async function api(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const response = await fetch(API + path, {
    ...rest,
    headers: { "Content-Type": "application/json", ...headers },
  });
  let body = null;
  try { body = await response.json(); } catch (e) { /* no JSON body */ }
  if (!response.ok) {
    throw new Error((body && body.error) || `Request failed (${response.status})`);
  }
  return body;
}

function rupees(amount) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(amount);
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

// ---- cart: a list of {id, qty} kept in the browser
function getCart() {
  try { return JSON.parse(localStorage.getItem(CART_KEY)) || []; } catch (e) { return []; }
}
function saveCart(cart) {
  localStorage.setItem(CART_KEY, JSON.stringify(cart.filter((i) => i.qty > 0)));
  updateCartCount();
}
function addToCart(productId, qty = 1) {
  const cart = getCart();
  const line = cart.find((i) => i.id === productId);
  if (line) line.qty = Math.min(10, line.qty + qty);
  else cart.push({ id: productId, qty: Math.min(10, qty) });
  saveCart(cart);
}
function cartCount() {
  return getCart().reduce((sum, i) => sum + i.qty, 0);
}
function updateCartCount() {
  document.querySelectorAll(".cart-count").forEach((el) => { el.textContent = cartCount(); });
}

function stockLabel(stock) {
  if (stock <= 0) return '<span class="stock out">Out of stock</span>';
  if (stock < 5) return `<span class="stock low">Only ${stock} left</span>`;
  return '<span class="stock">In stock</span>';
}

function showMessage(el, text, kind = "error") {
  el.innerHTML = `<div class="msg ${kind}">${escapeHtml(text)}</div>`;
}

// ---- header and footer, the same on every page
function renderLayout(activePage) {
  const header = document.getElementById("site-header");
  if (header) {
    header.className = "site-header";
    header.innerHTML = `
      <div class="container">
        <a class="logo" href="index.html">Shop<span>Ease</span></a>
        <nav class="nav">
          <a href="index.html" class="${activePage === "shop" ? "active" : ""}">Shop</a>
          <a href="order.html" class="${activePage === "track" ? "active" : ""}">Track order</a>
          <a href="cart.html" class="cart-link">Cart<span class="cart-count">0</span></a>
        </nav>
      </div>`;
  }
  const footer = document.getElementById("site-footer");
  if (footer) {
    footer.className = "site-footer";
    footer.innerHTML = `
      <div class="container">
        <span>&copy; ShopEase: a demo store for the DevOps with Multi-Cloud + GenAI course</span>
        <span id="server-info">Checking server...</span>
      </div>`;
    api("/health")
      .then((h) => { document.getElementById("server-info").textContent = `API v${h.version} on ${h.server} (${h.engine})`; })
      .catch(() => { document.getElementById("server-info").textContent = "API is not reachable"; });
  }
  updateCartCount();
}
