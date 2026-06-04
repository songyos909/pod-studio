"""รายการสินค้าดิจิทัล (ไฟล์ + ราคา) เก็บใน output/store/products.json.

สินค้า 1 ชิ้น = ไฟล์ที่ลูกค้าจะได้ดาวน์โหลด (PDF/ZIP/PNG) + ราคา + รูปพรีวิว.
"""

import json
import os
import uuid

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE_DIR = os.path.join(PROJECT_ROOT, "output", "store")
PRODUCTS_PATH = os.path.join(STORE_DIR, "products.json")

# ฟิลด์ของสินค้า 1 ชิ้น
# id, title, description, price (หน่วยเต็ม เช่น 99 = 99 บาท), currency,
# file (relpath ไฟล์ที่ส่งให้ลูกค้า), preview (relpath/หรือ url รูปโชว์), active (bool)


def _ensure_dir():
    os.makedirs(STORE_DIR, exist_ok=True)


def load_products():
    if not os.path.exists(PRODUCTS_PATH):
        return []
    with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def _save(products):
    _ensure_dir()
    with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def get_product(pid):
    return next((p for p in load_products() if p.get("id") == pid), None)


def _rel(path):
    """แปลงเป็น relpath อิงโปรเจกต์ (เก็บแบบ / เสมอ)."""
    if not path:
        return ""
    if os.path.isabs(path):
        path = os.path.relpath(path, PROJECT_ROOT)
    return path.replace("\\", "/")


def upsert_product(data):
    """เพิ่ม/แก้สินค้า. ถ้ามี id อยู่แล้ว = แก้, ไม่มี = เพิ่มใหม่. คืนสินค้าที่บันทึก."""
    products = load_products()
    pid = data.get("id")
    item = {
        "id": pid or uuid.uuid4().hex[:10],
        "title": (data.get("title") or "Untitled").strip(),
        "description": (data.get("description") or "").strip(),
        "price": max(0, int(float(data.get("price") or 0))),
        "currency": (data.get("currency") or "thb").lower(),
        "file": _rel(data.get("file") or ""),
        "preview": _rel(data.get("preview") or ""),
        "active": bool(data.get("active", True)),
    }
    if pid and any(p.get("id") == pid for p in products):
        products = [item if p.get("id") == pid else p for p in products]
    else:
        products.append(item)
    _save(products)
    return item


def delete_product(pid):
    products = load_products()
    kept = [p for p in products if p.get("id") != pid]
    if len(kept) == len(products):
        return False
    _save(kept)
    return True


def public_products():
    """รายการสินค้าที่เปิดขาย (ตัดข้อมูลไฟล์จริงออก ไม่ส่งให้ฝั่งลูกค้า)."""
    out = []
    for p in load_products():
        if not p.get("active"):
            continue
        out.append({
            "id": p["id"],
            "title": p["title"],
            "description": p["description"],
            "price": p["price"],
            "currency": p["currency"],
            "preview": ("/" + p["preview"]) if p.get("preview") else "",
        })
    return out
