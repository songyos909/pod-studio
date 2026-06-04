# Google Apps Script backend (รับออเดอร์เว็บร้าน)

โค้ด [Code.gs](Code.gs) เป็น backend ฟรีสำหรับรับคำสั่งซื้อจากหน้าร้าน → เก็บลง Google Sheet + ส่งอีเมลยืนยัน
**ทำทีหลังได้** — ตอนนี้ถ้ายังไม่ตั้ง ฟอร์มสั่งซื้อจะใช้การเปิดอีเมล (mailto) แทนไปก่อน

## วิธีติดตั้ง (ทำครั้งเดียว)
1. สร้าง **Google Sheet** ใหม่ (จะใช้เก็บออเดอร์)
2. ในชีตนั้นไปที่ **Extensions → Apps Script**
3. ลบโค้ดเดิม แล้ววางเนื้อหาจาก `Code.gs` ทั้งหมด
4. (ถ้าต้องการ) ใส่อีเมลร้านในตัวแปร `SHOP_EMAIL` ด้านบนไฟล์
5. กด **Deploy → New deployment**
   - Type: **Web app**
   - Execute as: **Me**
   - Who has access: **Anyone**
6. กด Deploy → อนุญาตสิทธิ์ (authorize) → ก๊อปลิงก์ที่ลงท้ายด้วย **`/exec`**
7. เอาลิงก์นั้นไปใส่ใน `config.yaml`:
   ```yaml
   site:
     gas_url: "https://script.google.com/macros/s/XXXX/exec"
   ```
8. สร้างเว็บร้านใหม่ (กดปุ่มในแท็บ "เว็บร้าน" หรือ `python src/build_site.py`)

เสร็จแล้วฟอร์มสั่งซื้อบนหน้าร้านจะส่งออเดอร์เข้า Google Sheet + อีเมลลูกค้าอัตโนมัติ

## หมายเหตุ
- Google Apps Script ไม่ส่ง CORS header กลับ — หน้าร้านจึงส่งแบบ `text/plain` และถือว่าสำเร็จถ้าส่งไม่ error
  (ออเดอร์จะถูกบันทึกแม้ browser อ่าน response ไม่ได้) ตรวจสอบได้จาก Google Sheet
- ปริมาณอีเมล/วันมี quota ของ Google (พอสำหรับร้านเล็ก–กลาง)
- ระบบจ่ายเงินจริง (PromptPay/Stripe) เป็นเฟสถัดไป — ดู [docs/website_plan.md](../docs/website_plan.md)
