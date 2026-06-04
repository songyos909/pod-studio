"""ระบบขายไฟล์ดิจิทัลบน PC (Stripe Checkout + ส่งไฟล์อัตโนมัติหลังจ่าย).

โมดูล:
- products : รายการสินค้า (สินค้าดิจิทัล = ไฟล์ + ราคา) เก็บใน output/store/products.json
- orders   : คำสั่งซื้อ + โทเคนดาวน์โหลด (กันแชร์/หมดอายุ/จำกัดครั้ง)
- payments : คุยกับ Stripe (สร้าง checkout session, ตรวจ webhook) + โหมดทดสอบ
"""
