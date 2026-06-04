# แผน: เว็บขายของตัวเอง (โดเมน + GitHub Pages + Google Apps Script)

> สถานะ: **เฟส 1 + โค้ด Apps Script ทำเสร็จบนเครื่องแล้ว** (storefront ใน `docs/`, `src/build_site.py`,
> `gas/Code.gs`) — รอเอาขึ้น GitHub Pages + deploy Apps Script ภายหลัง. เฟส 3-4 (จ่ายเงิน/โดเมน) ยังไม่ทำ
> เป้าหมาย: มีหน้าร้านเป็นของตัวเองโดยใช้ของฟรีให้มากที่สุด ค่าใช้จ่ายหลักคือโดเมน (~300–400 บาท/ปี)

## ภาพรวมสถาปัตยกรรม
```
[run_batch.py] --(catalog.csv + previews)--> [build_site.py]
       |                                            |
       |                                            v
       |                              docs/ (products.json + previews)
       |                                            |
       |                                   git push ขึ้น GitHub
       |                                            v
ลูกค้า --> โดเมนตัวเอง --> GitHub Pages (เว็บ static, ฟรี, HTTPS อัตโนมัติ)
                                            |
                              กดสั่งซื้อ (fetch POST)
                                            v
                         Google Apps Script Web App (/exec)
                                            |
                    +-----------------------+-----------------------+
                    v                       v                       v
            Google Sheet (ออเดอร์)   ส่งอีเมล (MailApp)      คืน QR/ลิงก์จ่ายเงิน
                                                                    |
                                            จ่ายแล้ว -> ส่งไฟล์ดาวน์โหลด (Google Drive)
```

## ส่วนประกอบ
| ส่วน | ใช้อะไร | ค่าใช้จ่าย |
|---|---|---|
| โฮสต์เว็บ (static) | **GitHub Pages** (โฟลเดอร์ `docs/`) | ฟรี |
| Backend (รับออเดอร์/อีเมล/ไฟล์) | **Google Apps Script** Web App | ฟรี (มี quota) |
| ฐานข้อมูลออเดอร์ | **Google Sheets** | ฟรี |
| เก็บไฟล์ส่งลูกค้า | **Google Drive** | ฟรี (15GB) |
| โดเมน | Cloudflare / Namecheap | ~300–400 บาท/ปี |
| รับเงิน | PromptPay QR / PayPal / Stripe Payment Link | ค่าธรรมเนียมตามเจ้า |

## โครงไฟล์ที่จะเพิ่ม (ตอน implement จริง)
```
docs/                    # = GitHub Pages root (ตั้งใน Settings > Pages > /docs)
├── index.html           # หน้าร้าน (โหลด products.json มาแสดง)
├── assets/              # css/js
├── previews/            # รูป preview (ก๊อปมาจาก output/)
└── products.json        # รายการสินค้า (สร้างจาก catalog.csv)
gas/
└── Code.gs              # โค้ด Apps Script (เอาไปวางใน script.google.com)
src/
└── build_site.py        # catalog.csv -> docs/products.json + ก๊อป previews
CNAME                    # โดเมน custom (GitHub Pages อ่านไฟล์นี้)
```

## Data flow โดยละเอียด
1. รัน `run_batch.py` → ได้ดีไซน์ + `output/catalog.csv` + preview
2. รัน `build_site.py` (ของอนาคต) → อ่าน catalog.csv → เขียน `docs/products.json` + ก๊อป preview ไป `docs/previews/`
3. `git push` → GitHub Pages อัปเดตเว็บอัตโนมัติ
4. ลูกค้าเปิดเว็บ → JS โหลด `products.json` มาเรนเดอร์การ์ดสินค้า
5. กด "สั่งซื้อ" → `fetch(POST)` ไปยัง Apps Script `/exec` (ส่ง ชื่อสินค้า/อีเมล/จำนวน)
6. Apps Script: `appendRow` ลง Google Sheet + `MailApp.sendEmail` ยืนยัน + คืน QR PromptPay / ลิงก์จ่ายเงิน
7. ลูกค้าจ่าย → ยืนยัน (แมนนวลจากสลิป หรืออัตโนมัติถ้าใช้ Stripe webhook) → ส่งลิงก์ไฟล์จาก Drive

## แผนทำเป็นเฟส
- **เฟส 1 (MVP):** `build_site.py` + หน้า `index.html` แสดงสินค้า + ปุ่มติดต่อสั่งซื้อ (LINE/อีเมล) — ขายได้แบบแมนนวลก่อน
- **เฟส 2:** Apps Script Web App รับฟอร์มออเดอร์ → Google Sheet + อีเมลยืนยัน
- **เฟส 3:** ระบบจ่ายเงิน (PromptPay QR / PayPal / Stripe link) + ส่งไฟล์ดาวน์โหลดอัตโนมัติ
- **เฟส 4:** ผูกโดเมน custom + ใส่ CNAME + ตั้ง DNS + SEO/meta tags

## ข้อควรรู้ / ข้อจำกัด
- GitHub Pages เสิร์ฟไฟล์ static เท่านั้น (ไม่มี server-side) → ต้องพึ่ง Apps Script เป็น backend
- Apps Script มี quota รายวัน (อีเมล/เวลา execution) — พอสำหรับร้านเล็ก–กลาง
- การรับเงินด้วยบัตรต้องใช้ตัวกลาง (Stripe/PayPal) — Apps Script รับเงินเองไม่ได้
- สำหรับตลาดไทย: PromptPay QR + อัปโหลดสลิป + ยืนยันใน Sheet เป็นแนวทางที่ทำได้จริงและถูก
- ไฟล์ print จริง (4500×5400) ใหญ่ — ส่งให้ลูกค้าผ่านลิงก์ Drive หลังยืนยันการจ่าย ไม่ฝังในเว็บ

## เชื่อมกับระบบปัจจุบันยังไง
- `output/catalog.csv` เป็น single source of truth อยู่แล้ว → `build_site.py` แค่แปลงเป็น `products.json`
- ใช้ `preview_path` (JPG เล็ก) เป็นรูปหน้าร้าน, ใช้ `image_path` (PNG ใหญ่) เป็นไฟล์ส่งมอบหลังขาย
- ทำคู่ขนานกับการลงขาย Etsy/Shopify ได้ (เว็บตัวเอง = ช่องทางเพิ่ม ไม่เสียค่าคอมมิชชั่น)
