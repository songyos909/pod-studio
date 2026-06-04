# ตั้งร้านขายไฟล์ดิจิทัลอัตโนมัติ 24 ชม. (ฟรี ไม่ต้องเปิดคอม)

ใช้ **GitHub Pages** (หน้าร้าน) + **Google Apps Script** (จ่าย+ส่งไฟล์) + **Google Drive** (เก็บไฟล์) + **Stripe** (รับเงิน)
ลูกค้าจ่ายผ่าน Stripe → ระบบส่งไฟล์ให้อัตโนมัติทางอีเมล + ลิงก์ Drive แม้คุณปิดคอม

> สิ่งที่คุณต้องมี: บัญชี Google (มีแล้ว), บัญชี Stripe (สมัครฟรีที่ stripe.com), repo GitHub Pages (มีแล้ว: songyos909/pod-studio)

---

## ขั้นที่ 1 — สร้าง Google Sheet (คลังสินค้า + บันทึกการขาย)
1. ไป https://sheets.google.com → สร้างไฟล์ใหม่ ตั้งชื่อ "POD Store"
2. แท็บแรกเปลี่ยนชื่อเป็น **`Products`** ใส่หัวคอลัมน์แถวแรก (ตรงเป๊ะ ตัวเล็ก):
   ```
   id   title   description   price   currency   image_url   drive_file_id   gumroad_url   active
   ```
3. กรอกสินค้า — หรือ **ลัด**: ในแอป POD Studio แท็บ "ร้านขาย" กด **"ดาวน์โหลดตาราง Products"** ได้ไฟล์ `.tsv` แล้วเปิดด้วย Notepad → ก๊อปทั้งหมด → วางในชีต `Products` (ช่อง A1) จะเติม id/title/price/image_url ให้อัตโนมัติ
   - `drive_file_id` = เว้นไว้ก่อน (เติมในขั้นที่ 2)
   - `gumroad_url` = ใส่เฉพาะสินค้าที่จะขายผ่าน Gumroad (ถ้าใส่ จะไม่ใช้ Stripe กับชิ้นนั้น)
   - `active` = `true` เพื่อเปิดขาย

> หมายเหตุ: ราคาเป็นจำนวนเต็มหน่วยปกติ เช่น `99` = 99 บาท (ระบบคูณ 100 เป็นสตางค์ให้เอง)

## ขั้นที่ 2 — อัปไฟล์สินค้าขึ้น Google Drive
1. สร้างโฟลเดอร์ใน Drive เช่น "POD Files" → อัปไฟล์ที่จะขาย (PDF/ZIP/PNG)
2. คลิกขวาไฟล์ → **Share → General access: Anyone with the link → Viewer** (ระบบจะตั้งให้อัตโนมัติด้วย แต่ตั้งเองไว้ก่อนชัวร์กว่า)
3. เอา **file id** มาใส่ชีต: เปิดไฟล์ → ดู URL `https://drive.google.com/file/d/`**`FILE_ID`**`/view` → ก๊อป `FILE_ID` ไปวางคอลัมน์ `drive_file_id` ของสินค้านั้น

## ขั้นที่ 3 — วางโค้ด Store.gs
1. ในไฟล์ Sheet เดิม: เมนู **Extensions → Apps Script**
2. ลบโค้ดเดิมทิ้ง → วางทั้งหมดจากไฟล์ `gas/Store.gs` ในโปรเจกต์นี้ → บันทึก (Ctrl+S)

## ขั้นที่ 4 — ใส่คีย์ Stripe ใน Script Properties (ปลอดภัย ไม่โผล่หน้าเว็บ)
1. ขอคีย์ที่ https://dashboard.stripe.com/apikeys (เริ่มที่ **Test mode** ก่อน) → ก๊อป **Secret key** (`sk_test_...`)
2. ใน Apps Script: ไอคอนเฟือง **Project Settings → Script Properties → Add script property** เพิ่มทีละคู่:

   | Property | Value |
   |---|---|
   | `STRIPE_SECRET` | `sk_test_...` (ของคุณ) |
   | `SHOP_EMAIL` | อีเมลรับแจ้งยอดขาย (เช่น songyos909@gmail.com) |
   | `CURRENCY` | `thb` |
   | `SHOP_NAME` | ชื่อร้านคุณ |
   | `SUCCESS_URL` | `https://songyos909.github.io/pod-studio/store/success.html` |
   | `CANCEL_URL` | `https://songyos909.github.io/pod-studio/store/` |
   | `WEBHOOK_KEY` | ตั้งรหัสลับอะไรก็ได้ เช่น `mysecret123` (ใช้ขั้นที่ 6) |
   | `EMAIL_FILES` | (ไม่บังคับ) ใส่ `false` ถ้า**ไม่อยากส่งอีเมล** — ลูกค้าโหลดบนหน้า success อย่างเดียว |

> 📌 ลูกค้าได้ไฟล์ "ทันทีบนหน้าจอ" หลังจ่ายเสมอ (ไม่ต้องเช็กอีเมล) — อีเมลเป็นแค่สำเนาสำรอง เผื่อปิดหน้าไปก่อนโหลด

## ขั้นที่ 5 — Deploy เป็น Web app
1. Apps Script → **Deploy → New deployment → ⚙️ → Web app**
2. ตั้ง: **Execute as: Me** , **Who has access: Anyone**
3. กด Deploy → **Authorize access** → ล็อกอิน Google ของคุณ → อนุญาต (ครั้งแรกจะมีคำเตือน "unverified" → Advanced → Go to project → Allow)
4. ก๊อป **Web app URL** (ลงท้าย `/exec`)
5. เอา URL นี้ใส่ `config.yaml → site.store_gas_url` และตั้ง `site.pages_base_url: "https://songyos909.github.io/pod-studio/"`
6. รัน `python src/build_site.py` แล้ว push:
   ```powershell
   cd D:\automate_video
   python src/build_site.py
   git add -A; git commit -m "setup digital store"; git push
   ```
   หน้าร้านจะ live ที่ **https://songyos909.github.io/pod-studio/store/**

## ขั้นที่ 6 — (สำรอง) ตั้ง Stripe Webhook กันลูกค้าปิดแท็บก่อนได้ไฟล์
> ไม่บังคับ — ระบบส่งไฟล์ตอนลูกค้ากลับมาหน้า success อยู่แล้ว แต่ webhook ช่วยกรณีปิดแท็บ
1. https://dashboard.stripe.com/webhooks → Add endpoint
2. URL: `https://....../exec?key=mysecret123` (ใส่ `WEBHOOK_KEY` ที่ตั้งไว้)
3. Event: `checkout.session.completed` → Add

## ขั้นที่ 7 — ทดสอบ (Test mode)
1. เปิด https://songyos909.github.io/pod-studio/store/ → เพิ่มสินค้าลงตะกร้า → ชำระเงิน
2. บัตรทดสอบ: **4242 4242 4242 4242** , วันหมดอายุอนาคต , CVC อะไรก็ได้ , ใส่อีเมลจริงของคุณ
3. จ่ายเสร็จ → หน้า success โชว์ลิงก์ดาวน์โหลด + เช็คอีเมลต้องได้ไฟล์แนบ/ลิงก์
4. เปิดชีต `Sales` ต้องมีแถวใหม่ (delivered = Y)

## ขั้นที่ 8 — เปิดขายจริง
1. ใน Stripe สลับเป็น **Live mode** → ขอ Secret key ใหม่ (`sk_live_...`)
2. แก้ Script Property `STRIPE_SECRET` เป็นคีย์ live → **Deploy → Manage deployments → Edit → New version → Deploy** (สำคัญ: ต้อง deploy เวอร์ชันใหม่ทุกครั้งที่แก้โค้ด/พร็อพเพอร์ตี้บางกรณี)
3. (ถ้าใช้ webhook) เพิ่ม endpoint แบบ live ด้วย

---

## ขายผ่าน Gumroad แทน (ทางเลือกที่ง่ายที่สุด — ไม่ต้องตั้ง Stripe/Drive)
1. สมัคร https://gumroad.com → New product → อัปไฟล์ + ตั้งราคา → Publish → ก๊อปลิงก์สินค้า
2. วางลิงก์ในชีต `Products` คอลัมน์ `gumroad_url` ของสินค้านั้น (ใส่ `drive_file_id` หรือไม่ก็ได้)
3. หน้าร้านจะขึ้นปุ่ม "ซื้อ & ดาวน์โหลด" ลิงก์ไป Gumroad — Gumroad จัดการจ่าย+ส่งไฟล์เองทั้งหมด

> ผสมได้: บางสินค้าใช้ Stripe (ของเราเอง) บางสินค้าใช้ Gumroad — แล้วแต่ใส่คอลัมน์ไหน

## แก้ปัญหาที่พบบ่อย
- **หน้าร้านว่าง / "ร้านยังไม่พร้อม"** → ยังไม่ได้ใส่ `store_gas_url` หรือยังไม่ build_site+push
- **กดจ่ายแล้วขึ้น error** → ยังไม่ได้ใส่ `STRIPE_SECRET` หรือ deploy เวอร์ชันเก่า → Deploy เวอร์ชันใหม่
- **จ่ายแล้วไม่ได้ไฟล์** → `drive_file_id` ผิด หรือไฟล์ไม่ได้ Share "Anyone with link"
- **แก้โค้ด/พร็อพแล้วไม่อัปเดต** → ต้อง **Manage deployments → New version** เสมอ (ไม่ใช่แค่บันทึก)
- **ไฟล์ใหญ่ >24MB** → อีเมลจะแนบไม่ได้ แต่ลิงก์ Drive ยังส่งให้ (ลูกค้าโหลดจากลิงก์)
