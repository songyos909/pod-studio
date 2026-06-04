// ร้านค้า static — โหลด data.json (สร้างโดย build_site.py) แล้วแสดงสินค้า + ฟอร์มสั่งซื้อ
let SHOP = {};
let CURRENT = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const money = (p) => `${SHOP.currency || ""} ${p}`.trim();

async function init() {
  let data;
  try {
    data = await (await fetch("data.json", { cache: "no-store" })).json();
  } catch (e) {
    $("empty").style.display = "block";
    $("empty").textContent = "ยังไม่ได้สร้างข้อมูลร้าน (รัน build_site)";
    return;
  }
  SHOP = data.shop || {};
  document.title = SHOP.name || "ร้านดีไซน์";
  $("shop-name").textContent = SHOP.name || "ร้านดีไซน์";
  $("shop-intro").textContent = SHOP.intro || "";
  $("shop-contact").textContent = contactText();

  const products = data.products || [];
  if (!products.length) { $("empty").style.display = "block"; return; }
  $("grid").innerHTML = products.map((p, i) => `
    <div class="product" data-i="${i}">
      <img src="${esc(p.image)}" loading="lazy" alt="${esc(p.title)}" />
      <div class="info"><b>${esc(p.title)}</b><span class="price">${esc(money(p.price))}</span></div>
    </div>`).join("");
  document.querySelectorAll(".product").forEach((el) => {
    el.onclick = () => openModal(products[+el.dataset.i]);
  });
}

function contactText() {
  const bits = [];
  if (SHOP.contact_email) bits.push("อีเมล: " + SHOP.contact_email);
  if (SHOP.line_id) bits.push("LINE: " + SHOP.line_id);
  return bits.join("  •  ");
}

function openModal(p) {
  CURRENT = p;
  $("m-img").src = p.image;
  $("m-title").textContent = p.title;
  $("m-price").textContent = money(p.price);
  $("m-tags").innerHTML = (p.tags || "").split(",").filter(Boolean)
    .map((t) => `<span>${esc(t.trim())}</span>`).join("");
  $("order-msg").textContent = "";
  $("order-form").reset();
  $("modal").style.display = "flex";
}
function closeModal() { $("modal").style.display = "none"; }

$("modal-close").onclick = closeModal;
$("modal").onclick = (e) => { if (e.target.id === "modal") closeModal(); };

$("order-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const order = {
    title: CURRENT.title, slug: CURRENT.slug, price: CURRENT.price,
    name: f.name.value, email: f.email.value,
    qty: parseInt(f.qty.value) || 1, note: f.note.value,
  };
  const msg = $("order-msg");

  // ยังไม่ได้ตั้ง Google Apps Script -> ใช้อีเมล/ติดต่อแทน
  if (!SHOP.gas_url) {
    if (SHOP.contact_email) {
      const subject = encodeURIComponent(`สั่งซื้อ: ${order.title}`);
      const body = encodeURIComponent(
        `สินค้า: ${order.title}\nจำนวน: ${order.qty}\nชื่อ: ${order.name}\nอีเมล: ${order.email}\nหมายเหตุ: ${order.note}`);
      window.location.href = `mailto:${SHOP.contact_email}?subject=${subject}&body=${body}`;
      msg.className = "order-msg ok";
      msg.textContent = "กำลังเปิดอีเมลเพื่อส่งคำสั่งซื้อ...";
    } else {
      msg.className = "order-msg err";
      msg.textContent = "ร้านยังไม่ได้ตั้งช่องทางรับออเดอร์ (gas_url / contact_email)";
    }
    return;
  }

  // ส่งไป Google Apps Script — ใช้ text/plain เพื่อเลี่ยง CORS preflight
  msg.className = "order-msg";
  msg.textContent = "กำลังส่งคำสั่งซื้อ...";
  try {
    await fetch(SHOP.gas_url, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(order),
    });
    // GAS อาจไม่ส่ง CORS header กลับ — ถือว่าสำเร็จถ้าส่งไม่ error
    msg.className = "order-msg ok";
    msg.textContent = "✅ ส่งคำสั่งซื้อแล้ว! เราจะติดต่อกลับทางอีเมลเรื่องชำระเงิน/จัดส่ง";
    f.reset();
  } catch (err) {
    msg.className = "order-msg err";
    msg.textContent = "ส่งไม่สำเร็จ ลองใหม่ หรือติดต่อร้านโดยตรง";
  }
};

init();
