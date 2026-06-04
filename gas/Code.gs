/**
 * POD Store — Google Apps Script backend (รับออเดอร์จากเว็บร้าน)
 *
 * หน้าที่: รับ POST จากหน้าร้าน -> บันทึกลง Google Sheet + ส่งอีเมลยืนยัน
 * วิธีติดตั้ง: ดู gas/README.md  (สรุป: สร้าง Sheet -> Extensions > Apps Script ->
 *   วางโค้ดนี้ -> Deploy > Web app (Execute as: Me, Who has access: Anyone) ->
 *   ก๊อปลิงก์ /exec ไปใส่ config.yaml site.gas_url แล้ว build_site ใหม่)
 */

// ====== ตั้งค่า ======
var SHOP_EMAIL = "";          // อีเมลร้าน (รับแจ้งเตือนออเดอร์ใหม่) — เว้นว่างได้
var SHEET_NAME = "Orders";    // ชื่อชีตเก็บออเดอร์

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var orderId = "ORD-" + Date.now();

    var sheet = getSheet_();
    sheet.appendRow([
      new Date(), orderId, data.title || "", data.slug || "",
      data.qty || 1, data.price || "", data.name || "", data.email || "", data.note || "",
    ]);

    // อีเมลยืนยันถึงลูกค้า
    if (data.email) {
      MailApp.sendEmail(
        data.email,
        "ยืนยันคำสั่งซื้อ " + orderId,
        "ขอบคุณสำหรับคำสั่งซื้อ!\n\n" +
        "เลขที่ออเดอร์: " + orderId + "\n" +
        "สินค้า: " + (data.title || "") + "\n" +
        "จำนวน: " + (data.qty || 1) + "\n\n" +
        "เราจะติดต่อกลับเรื่องการชำระเงินและการจัดส่งครับ"
      );
    }

    // แจ้งเตือนร้าน
    if (SHOP_EMAIL) {
      MailApp.sendEmail(SHOP_EMAIL, "ออเดอร์ใหม่ " + orderId,
        JSON.stringify(data, null, 2));
    }

    return json_({ ok: true, order_id: orderId });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function doGet(e) {
  return json_({ ok: true, service: "POD Store backend" });
}

function getSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(["timestamp", "order_id", "title", "slug", "qty", "price", "name", "email", "note"]);
  }
  return sh;
}

function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
