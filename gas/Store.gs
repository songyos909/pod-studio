/**
 * POD Digital Store — Google Apps Script backend (serverless, ฟรี 24 ชม.)
 *
 * ขายไฟล์ดิจิทัลผ่าน Stripe โดยไม่ต้องเปิดคอม:
 *   หน้าร้าน (GitHub Pages) -> GAS สร้าง Stripe Checkout -> ลูกค้าจ่าย ->
 *   GAS ยืนยันกับ Stripe -> ส่งไฟล์จาก Google Drive (อีเมลแนบ + ลิงก์) -> log ลง Sheet
 *
 * ติดตั้ง: ดู gas/STORE_SETUP.md (สรุป: สร้าง Sheet 2 แท็บ Products/Sales ->
 *   วางโค้ดนี้ -> ตั้ง Script Properties (STRIPE_SECRET ฯลฯ) ->
 *   Deploy > Web app (Execute as: Me, Who has access: Anyone) ->
 *   ก๊อปลิงก์ /exec ใส่ config.yaml site.store_gas_url)
 *
 * ความปลอดภัย:
 *  - คีย์ Stripe อยู่ใน Script Properties เท่านั้น (ไม่อยู่ฝั่ง client)
 *  - ราคา/ไฟล์อ่านจาก Sheet ฝั่งเซิร์ฟเวอร์ (frontend ส่งแค่ id กันปลอมราคา)
 *  - ก่อนส่งไฟล์ "ทุกครั้ง" ดึง session จาก Stripe มาเช็ก payment_status=paid
 *    (กันคนยิง confirm/webhook ปลอม)
 */

var SHEET_PRODUCTS = "Products";
var SHEET_SALES = "Sales";
var STRIPE_API = "https://api.stripe.com/v1";
var ATTACH_LIMIT = 24 * 1024 * 1024; // ไฟล์ ≤24MB แนบอีเมลได้ ไม่งั้นส่งลิงก์อย่างเดียว

// ---------- config จาก Script Properties ----------
function getCfg_() {
  var p = PropertiesService.getScriptProperties();
  return {
    secret: p.getProperty("STRIPE_SECRET") || "",
    webhookKey: p.getProperty("WEBHOOK_KEY") || "",
    shopEmail: p.getProperty("SHOP_EMAIL") || "",
    currency: (p.getProperty("CURRENCY") || "thb").toLowerCase(),
    successUrl: p.getProperty("SUCCESS_URL") || "",   // เช่น https://user.github.io/pod-studio/store/success.html
    cancelUrl: p.getProperty("CANCEL_URL") || "",     // เช่น https://user.github.io/pod-studio/store/
    shopName: p.getProperty("SHOP_NAME") || "Digital Store",
    emailFiles: p.getProperty("EMAIL_FILES") !== "false" // "false" = ไม่ส่งอีเมล (ลูกค้าโหลดหน้า success อย่างเดียว)
  };
}

// ====================== ROUTES ======================
function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || "products";
  try {
    if (action === "products") return json_({ ok: true, products: listProducts_() });
    if (action === "checkout") return checkout_(e);
    if (action === "confirm") return json_(confirm_(e.parameter.session_id));
    return json_({ ok: true, service: "POD Digital Store" });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doPost(e) {
  // webhook สำรองจาก Stripe — ป้องกันด้วย ?key= + re-verify เสมอใน deliver_
  try {
    var cfg = getCfg_();
    if (!cfg.webhookKey || (e.parameter && e.parameter.key) !== cfg.webhookKey) {
      return json_({ ok: false, error: "unauthorized" });
    }
    var ev = JSON.parse(e.postData.contents);
    var obj = ev && ev.data && ev.data.object ? ev.data.object : {};
    var sid = obj.id || (ev && ev.id);
    if (sid && String(sid).indexOf("cs_") === 0) deliver_(sid);
    return json_({ received: true });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

// ====================== PRODUCTS ======================
function productRows_() {
  var sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_PRODUCTS);
  if (!sh) throw new Error("ไม่พบชีต " + SHEET_PRODUCTS);
  var values = sh.getDataRange().getValues();
  var head = values.shift().map(function (h) { return String(h).trim().toLowerCase(); });
  return values.map(function (row) {
    var o = {};
    head.forEach(function (h, i) { o[h] = row[i]; });
    return o;
  }).filter(function (o) { return o.id; });
}

function listProducts_() {
  return productRows_()
    .filter(function (p) { return String(p.active).toLowerCase() !== "false" && String(p.active) !== "0"; })
    .map(function (p) {
      return {
        id: String(p.id),
        title: String(p.title || ""),
        description: String(p.description || ""),
        price: Number(p.price) || 0,
        currency: String(p.currency || getCfg_().currency).toLowerCase(),
        image: String(p.image_url || ""),
        gumroad_url: String(p.gumroad_url || "")
        // ไม่ส่ง drive_file_id ออกไปฝั่ง client
      };
    });
}

function findProduct_(id) {
  var rows = productRows_();
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i].id) === String(id)) return rows[i];
  }
  return null;
}

// ====================== CHECKOUT ======================
function checkout_(e) {
  var cfg = getCfg_();
  if (!cfg.secret) return htmlError_("ร้านยังไม่ได้ตั้งคีย์ Stripe");
  var ids = String((e.parameter.items || "")).split(",").map(function (s) { return s.trim(); }).filter(String);
  if (!ids.length) return htmlError_("ไม่มีสินค้าที่เลือก");

  var items = [], zeroDecimal = { jpy: 1, krw: 1, vnd: 1, clp: 1 };
  for (var i = 0; i < ids.length; i++) {
    var p = findProduct_(ids[i]);
    if (!p || !p.drive_file_id) continue;     // ขายเฉพาะสินค้าที่มีไฟล์จริง
    if (p.gumroad_url) continue;              // สินค้า Gumroad ไม่ผ่าน Stripe
    var cur = String(p.currency || cfg.currency).toLowerCase();
    var unit = zeroDecimal[cur] ? Math.round(Number(p.price)) : Math.round(Number(p.price) * 100);
    items.push({ id: String(p.id), title: String(p.title || "Digital product"), currency: cur, unit: unit });
  }
  if (!items.length) return htmlError_("ไม่พบสินค้าที่ขายผ่าน Stripe");

  var cur = items[0].currency;
  var payload = {
    "mode": "payment",
    "success_url": cfg.successUrl + "?session_id={CHECKOUT_SESSION_ID}",
    "cancel_url": cfg.cancelUrl,
    "metadata[items]": items.map(function (it) { return it.id; }).join(","),
    "payment_method_types[0]": "card"
  };
  if (cur === "thb") payload["payment_method_types[1]"] = "promptpay";
  items.forEach(function (it, i) {
    payload["line_items[" + i + "][quantity]"] = "1";
    payload["line_items[" + i + "][price_data][currency]"] = it.currency;
    payload["line_items[" + i + "][price_data][unit_amount]"] = String(it.unit);
    payload["line_items[" + i + "][price_data][product_data][name]"] = it.title;
  });

  var res = stripe_("POST", "/checkout/sessions", payload);
  if (!res.url) return htmlError_("สร้างการชำระเงินไม่สำเร็จ: " + (res.error ? res.error.message : "unknown"));
  return redirect_(res.url);
}

// ====================== CONFIRM + DELIVER ======================
function confirm_(sessionId) {
  if (!sessionId) return { ok: false, error: "ไม่มี session_id" };
  return deliver_(sessionId);
}

function deliver_(sessionId) {
  var cfg = getCfg_();
  var s = stripe_("GET", "/checkout/sessions/" + encodeURIComponent(sessionId), null);
  if (!s || s.error) return { ok: false, error: "ตรวจสอบ session ไม่ได้" };
  if (s.payment_status !== "paid") return { ok: false, paid: false, status: s.payment_status };

  var email = (s.customer_details && s.customer_details.email) || s.customer_email || "";
  var amount = (s.amount_total != null) ? s.amount_total : "";
  var itemIds = (s.metadata && s.metadata.items) ? String(s.metadata.items).split(",") : [];

  // idempotent: ถ้า session นี้ส่งแล้ว คืนผลเดิม ไม่ส่งซ้ำ
  var sales = getSheet_(SHEET_SALES, ["timestamp", "session_id", "email", "items", "amount", "delivered"]);
  var existing = sales.getDataRange().getValues();
  for (var r = 1; r < existing.length; r++) {
    if (String(existing[r][1]) === String(sessionId)) {
      return { ok: true, paid: true, already: true, email: email,
               items: itemIds.map(function (id) { var p = findProduct_(id); return { title: p ? String(p.title) : id }; }) };
    }
  }

  // เตรียมไฟล์ + ลิงก์
  var delivered = [], attachments = [], linksHtml = [];
  itemIds.forEach(function (id) {
    var p = findProduct_(id);
    if (!p || !p.drive_file_id) return;
    try {
      var file = DriveApp.getFileById(String(p.drive_file_id).trim());
      try { file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW); } catch (e2) {}
      var link = "https://drive.google.com/uc?export=download&id=" + file.getId();
      linksHtml.push('<li><b>' + esc_(p.title) + '</b> — <a href="' + link + '">ดาวน์โหลด</a></li>');
      if (file.getSize() <= ATTACH_LIMIT) attachments.push(file.getAs(file.getMimeType()));
      delivered.push({ title: String(p.title), link: link });
    } catch (e3) {
      linksHtml.push('<li>' + esc_(p.title) + ' — (ไฟล์มีปัญหา ติดต่อร้าน)</li>');
    }
  });

  // ส่งอีเมลลูกค้า (สำรอง) — ลูกค้าโหลดได้เลยบนหน้า success อยู่แล้ว
  // ปิดได้ด้วย Script Property EMAIL_FILES = false
  if (email && cfg.emailFiles) {
    var body = '<p>ขอบคุณสำหรับการสั่งซื้อจาก ' + esc_(cfg.shopName) + '!</p>' +
      '<p>ดาวน์โหลดไฟล์ของคุณ:</p><ul>' + linksHtml.join("") + '</ul>' +
      '<p>หมายเลขคำสั่งซื้อ: ' + esc_(sessionId) + '</p>';
    MailApp.sendEmail({
      to: email,
      subject: "ไฟล์ดาวน์โหลดจาก " + cfg.shopName,
      htmlBody: body,
      attachments: attachments
    });
  }
  if (cfg.shopEmail) {
    MailApp.sendEmail(cfg.shopEmail, "ขายได้! " + sessionId,
      "email: " + email + "\namount: " + amount + "\nitems: " + itemIds.join(", "));
  }

  sales.appendRow([new Date(), sessionId, email, itemIds.join(", "), amount, "Y"]);
  return { ok: true, paid: true, email: email, emailed: !!(email && cfg.emailFiles),
           items: delivered.map(function (d) { return { title: d.title, link: d.link }; }) };
}

// ====================== STRIPE HELPERS ======================
function stripe_(method, path, payload) {
  var cfg = getCfg_();
  var opt = {
    method: method,
    headers: { Authorization: "Bearer " + cfg.secret },
    muteHttpExceptions: true
  };
  if (payload) opt.payload = payload; // UrlFetchApp encode เป็น x-www-form-urlencoded ให้เอง
  var resp = UrlFetchApp.fetch(STRIPE_API + path, opt);
  try { return JSON.parse(resp.getContentText()); }
  catch (e) { return { error: { message: resp.getContentText() } }; }
}

// ====================== UTIL ======================
function getSheet_(name, header) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); if (header) sh.appendRow(header); }
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function redirect_(url) {
  // เปลี่ยนหน้าไป Stripe (เลี่ยง CORS เพราะเป็นการ navigate ทั้งหน้า)
  var html = '<!doctype html><meta charset="utf-8">' +
    '<title>กำลังไปหน้าชำระเงิน...</title>' +
    '<script>location.replace(' + JSON.stringify(url) + ');</script>' +
    '<p>กำลังพาไปหน้าชำระเงิน... ถ้าไม่เด้ง <a href="' + esc_(url) + '">คลิกที่นี่</a></p>';
  return HtmlService.createHtmlOutput(html)
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function htmlError_(msg) {
  return HtmlService.createHtmlOutput('<meta charset="utf-8"><p style="font-family:sans-serif">⚠️ ' + esc_(msg) + '</p>');
}

function esc_(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
