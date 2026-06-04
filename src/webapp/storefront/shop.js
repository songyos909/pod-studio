const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let PRODUCTS = [];
let CURRENCY = "thb";
let cart = [];  // product ids

function money(n) {
  const sym = { thb: "฿", usd: "$", eur: "€" }[CURRENCY] || "";
  return sym + Number(n).toLocaleString();
}

async function init() {
  try {
    const info = await fetch("/store/api/info").then((r) => r.json());
    CURRENCY = info.currency || "thb";
    $("shop-name").textContent = info.shop_name || "ร้านค้า";
    document.title = info.shop_name || "ร้านค้า";
    if (info.intro) $("shop-intro").textContent = info.intro;
    if (info.mode === "mock") {
      const b = $("mode-banner");
      b.style.display = "block";
      b.textContent = "⚙️ โหมดทดสอบ: ยังไม่ได้ตั้งคีย์ Stripe — การชำระเงินเป็นการจำลอง (ไม่มีการเก็บเงินจริง)";
    } else if (info.mode === "test") {
      const b = $("mode-banner");
      b.style.display = "block";
      b.textContent = "🧪 โหมดทดสอบ Stripe: ใช้บัตรทดสอบ 4242 4242 4242 4242 (ไม่มีการเก็บเงินจริง)";
    }
  } catch (e) { /* ignore */ }

  const data = await fetch("/store/api/products").then((r) => r.json());
  PRODUCTS = data.products || [];
  renderProducts();
  loadCart();
}

function renderProducts() {
  if (!PRODUCTS.length) { $("empty").style.display = "block"; return; }
  $("products").innerHTML = PRODUCTS.map((p) => `
    <div class="card">
      <div class="thumb">${p.preview ? `<img src="${esc(p.preview)}" alt="${esc(p.title)}" />` : "📄"}</div>
      <div class="body">
        <h3>${esc(p.title)}</h3>
        <p class="desc">${esc(p.description || "")}</p>
        <div class="card-foot">
          <span class="price">${money(p.price)}</span>
          <button class="add-btn" data-id="${esc(p.id)}">เพิ่มลงตะกร้า</button>
        </div>
      </div>
    </div>`).join("");
  document.querySelectorAll(".add-btn").forEach((b) => {
    b.onclick = () => { addToCart(b.dataset.id); };
  });
}

function addToCart(id) {
  if (!cart.includes(id)) cart.push(id);
  saveCart();
  openCart();
}
function removeFromCart(id) { cart = cart.filter((x) => x !== id); saveCart(); renderCart(); }
function saveCart() { localStorage.setItem("shop_cart", JSON.stringify(cart)); updateCount(); }
function loadCart() {
  try { cart = JSON.parse(localStorage.getItem("shop_cart") || "[]"); } catch (e) { cart = []; }
  cart = cart.filter((id) => PRODUCTS.some((p) => p.id === id));
  updateCount();
}
function updateCount() { $("cart-count").textContent = cart.length; }

function cartProducts() { return cart.map((id) => PRODUCTS.find((p) => p.id === id)).filter(Boolean); }
function cartTotal() { return cartProducts().reduce((s, p) => s + p.price, 0); }

function renderCart() {
  const items = cartProducts();
  $("cart-total").textContent = money(cartTotal());
  if (!items.length) { $("cart-items").innerHTML = '<p class="empty">ตะกร้าว่าง</p>'; return; }
  $("cart-items").innerHTML = items.map((p) => `
    <div class="cart-row">
      <div class="ci-thumb">${p.preview ? `<img src="${esc(p.preview)}" />` : "📄"}</div>
      <div class="ci-info"><b>${esc(p.title)}</b><span>${money(p.price)}</span></div>
      <button class="ci-rm" data-id="${esc(p.id)}">✕</button>
    </div>`).join("");
  document.querySelectorAll(".ci-rm").forEach((b) => { b.onclick = () => removeFromCart(b.dataset.id); });
}

function openCart() { renderCart(); $("cart-overlay").style.display = "flex"; }
function closeCart() { $("cart-overlay").style.display = "none"; }

$("cart-btn").onclick = openCart;
$("cart-close").onclick = closeCart;
$("cart-overlay").onclick = (e) => { if (e.target.id === "cart-overlay") closeCart(); };

$("checkout-btn").onclick = async () => {
  if (!cart.length) { $("checkout-msg").textContent = "ตะกร้าว่าง"; return; }
  $("checkout-btn").disabled = true;
  $("checkout-msg").textContent = "กำลังไปหน้าชำระเงิน...";
  try {
    const r = await fetch("/store/api/checkout", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: cart }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || "เกิดข้อผิดพลาด");
    localStorage.removeItem("shop_cart");  // ล้างตะกร้าก่อนไปจ่าย
    location.href = d.url;
  } catch (e) {
    $("checkout-msg").textContent = "❌ " + e.message;
    $("checkout-btn").disabled = false;
  }
};

init();
