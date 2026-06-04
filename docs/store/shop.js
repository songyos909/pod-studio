// ร้านดาวน์โหลดดิจิทัล (static) — คุยกับ Google Apps Script (Stripe + Drive)
// config.js กำหนด window.STORE_CONFIG = { gas_url, shop_name, currency }
var CFG = window.STORE_CONFIG || {};
var GAS = CFG.gas_url || "";
var CURRENCY = (CFG.currency || "thb").toLowerCase();
var PRODUCTS = [];
var cart = [];

var $ = function (id) { return document.getElementById(id); };
var esc = function (s) { return (s || "").replace(/[&<>"]/g, function (c) { return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]; }); };
function money(n) {
  var sym = { thb: "฿", usd: "$", eur: "€" }[CURRENCY] || "";
  return sym + Number(n).toLocaleString();
}

async function init() {
  if (CFG.shop_name) { $("shop-name").textContent = CFG.shop_name; document.title = CFG.shop_name; }
  if (CFG.intro) $("shop-intro").textContent = CFG.intro;
  if (!GAS) {
    $("banner").style.display = "block";
    $("banner").textContent = "⚙️ ยังไม่ได้ตั้งค่า store_gas_url — ดู gas/STORE_SETUP.md";
    $("empty").style.display = "block"; $("empty").textContent = "ร้านยังไม่พร้อม";
    return;
  }
  try {
    var r = await fetch(GAS + "?action=products", { cache: "no-store" });
    var d = await r.json();
    PRODUCTS = (d.products || []);
  } catch (e) {
    $("empty").style.display = "block"; $("empty").textContent = "โหลดสินค้าไม่สำเร็จ";
    return;
  }
  renderProducts();
  loadCart();
}

function renderProducts() {
  if (!PRODUCTS.length) { $("empty").style.display = "block"; $("empty").textContent = "ยังไม่มีสินค้า"; return; }
  $("empty").style.display = "none";
  $("grid").innerHTML = PRODUCTS.map(function (p) {
    var btn = p.gumroad_url
      ? '<a class="add-btn gum" href="' + esc(p.gumroad_url) + '" target="_blank" rel="noopener">ซื้อ &amp; ดาวน์โหลด ↗</a>'
      : '<button class="add-btn" data-id="' + esc(p.id) + '">เพิ่มลงตะกร้า</button>';
    return '<div class="card">' +
      '<div class="thumb">' + (p.image ? '<img src="' + esc(p.image) + '" loading="lazy" alt="' + esc(p.title) + '"/>' : "📄") + '</div>' +
      '<div class="body"><h3>' + esc(p.title) + '</h3>' +
      '<p class="desc">' + esc(p.description || "") + '</p>' +
      '<div class="card-foot"><span class="price">' + money(p.price) + '</span>' + btn + '</div></div></div>';
  }).join("");
  document.querySelectorAll(".add-btn[data-id]").forEach(function (b) {
    b.onclick = function () { addToCart(b.dataset.id); };
  });
}

function addToCart(id) { if (cart.indexOf(id) < 0) cart.push(id); saveCart(); openCart(); }
function removeFromCart(id) { cart = cart.filter(function (x) { return x !== id; }); saveCart(); renderCart(); }
function saveCart() { localStorage.setItem("dstore_cart", JSON.stringify(cart)); updateCount(); }
function loadCart() {
  try { cart = JSON.parse(localStorage.getItem("dstore_cart") || "[]"); } catch (e) { cart = []; }
  cart = cart.filter(function (id) { return PRODUCTS.some(function (p) { return p.id === id; }); });
  updateCount();
}
function updateCount() { $("cart-count").textContent = cart.length; }
function cartProducts() { return cart.map(function (id) { return PRODUCTS.find(function (p) { return p.id === id; }); }).filter(Boolean); }
function cartTotal() { return cartProducts().reduce(function (s, p) { return s + Number(p.price); }, 0); }

function renderCart() {
  var items = cartProducts();
  $("cart-total").textContent = money(cartTotal());
  if (!items.length) { $("cart-items").innerHTML = '<p class="empty">ตะกร้าว่าง</p>'; return; }
  $("cart-items").innerHTML = items.map(function (p) {
    return '<div class="cart-row"><div class="ci-thumb">' + (p.image ? '<img src="' + esc(p.image) + '"/>' : "📄") + '</div>' +
      '<div class="ci-info"><b>' + esc(p.title) + '</b><span>' + money(p.price) + '</span></div>' +
      '<button class="ci-rm" data-id="' + esc(p.id) + '">✕</button></div>';
  }).join("");
  document.querySelectorAll(".ci-rm").forEach(function (b) { b.onclick = function () { removeFromCart(b.dataset.id); }; });
}
function openCart() { renderCart(); $("cart-overlay").style.display = "flex"; }
function closeCart() { $("cart-overlay").style.display = "none"; }

$("cart-btn").onclick = openCart;
$("cart-close").onclick = closeCart;
$("cart-overlay").onclick = function (e) { if (e.target.id === "cart-overlay") closeCart(); };

$("checkout-btn").onclick = function () {
  if (!cart.length) return;
  // navigate ทั้งหน้าไป GAS -> สร้าง Stripe session -> redirect ไป Stripe (เลี่ยง CORS)
  localStorage.removeItem("dstore_cart");
  location.href = GAS + "?action=checkout&items=" + encodeURIComponent(cart.join(","));
};

init();
