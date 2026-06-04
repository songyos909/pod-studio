"""คำสั่งซื้อ + โทเคนดาวน์โหลด เก็บใน output/store/orders.json.

หลังจ่ายเงินสำเร็จ (Stripe webhook) จะสร้างโทเคนดาวน์โหลดต่อสินค้า 1 ชิ้น
โทเคนมีวันหมดอายุ + จำกัดจำนวนครั้ง เพื่อกันการแชร์ลิงก์.
"""

import json
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORE_DIR = os.path.join(PROJECT_ROOT, "output", "store")
ORDERS_PATH = os.path.join(STORE_DIR, "orders.json")

_LOCK = threading.Lock()

# นโยบายดาวน์โหลด (override ได้จาก config.yaml > store)
DEFAULT_EXPIRY_DAYS = 30
DEFAULT_MAX_DOWNLOADS = 10


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


def _load():
    if not os.path.exists(ORDERS_PATH):
        return {"orders": {}, "tokens": {}}
    with open(ORDERS_PATH, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {"orders": {}, "tokens": {}}
    data.setdefault("orders", {})
    data.setdefault("tokens", {})
    return data


def _save(data):
    os.makedirs(STORE_DIR, exist_ok=True)
    tmp = ORDERS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ORDERS_PATH)


def create_order(items, session_id=None, currency="thb"):
    """สร้างออเดอร์สถานะ pending. items = [{id,title,price,file}, ...]. คืน order."""
    with _LOCK:
        data = _load()
        oid = "ord_" + secrets.token_hex(8)
        order = {
            "id": oid,
            "session_id": session_id,
            "status": "pending",
            "items": [{"id": i["id"], "title": i.get("title", ""),
                       "price": int(i.get("price", 0)), "file": i.get("file", "")} for i in items],
            "amount_total": sum(int(i.get("price", 0)) for i in items),
            "currency": currency,
            "email": "",
            "created_at": _iso(_now()),
            "paid_at": "",
            "downloads": [],  # โทเคนต่อสินค้า
        }
        data["orders"][oid] = order
        _save(data)
        return order


def set_session(order_id, session_id):
    with _LOCK:
        data = _load()
        o = data["orders"].get(order_id)
        if o:
            o["session_id"] = session_id
            _save(data)


def get_order(order_id):
    return _load()["orders"].get(order_id)


def get_by_session(session_id):
    if not session_id:
        return None
    for o in _load()["orders"].values():
        if o.get("session_id") == session_id:
            return o
    return None


def mark_paid(order_id, email="", amount_total=None,
              expiry_days=DEFAULT_EXPIRY_DAYS, max_downloads=DEFAULT_MAX_DOWNLOADS):
    """ทำเครื่องหมายว่าจ่ายแล้ว + สร้างโทเคนดาวน์โหลดต่อสินค้า. idempotent."""
    with _LOCK:
        data = _load()
        o = data["orders"].get(order_id)
        if not o:
            return None
        if o["status"] == "paid":
            return o  # กันยิงซ้ำ (webhook อาจมาหลายครั้ง)
        o["status"] = "paid"
        o["paid_at"] = _iso(_now())
        if email:
            o["email"] = email
        if amount_total is not None:
            o["amount_total"] = amount_total
        expires = _iso(_now() + timedelta(days=expiry_days))
        o["downloads"] = []
        for it in o["items"]:
            tok = secrets.token_urlsafe(24)
            o["downloads"].append({
                "token": tok, "product_id": it["id"], "title": it["title"],
                "file": it["file"], "expires_at": expires,
                "max_downloads": max_downloads, "count": 0,
            })
            data["tokens"][tok] = order_id
        _save(data)
        return o


def use_token(token):
    """ตรวจโทเคน + เพิ่มตัวนับ. คืน (ok, info, error).

    info = {file, title} เมื่อ ok=True.
    """
    with _LOCK:
        data = _load()
        oid = data["tokens"].get(token)
        if not oid:
            return False, None, "ลิงก์ดาวน์โหลดไม่ถูกต้อง"
        o = data["orders"].get(oid)
        if not o or o["status"] != "paid":
            return False, None, "ยังไม่ได้ชำระเงิน"
        dl = next((d for d in o["downloads"] if d["token"] == token), None)
        if not dl:
            return False, None, "ไม่พบรายการดาวน์โหลด"
        if datetime.fromisoformat(dl["expires_at"]) < _now():
            return False, None, "ลิงก์หมดอายุแล้ว"
        if dl["count"] >= dl["max_downloads"]:
            return False, None, "ดาวน์โหลดครบจำนวนครั้งที่กำหนดแล้ว"
        dl["count"] += 1
        _save(data)
        return True, {"file": dl["file"], "title": dl["title"]}, None


def list_orders(limit=200):
    orders = list(_load()["orders"].values())
    orders.sort(key=lambda o: o.get("created_at", ""), reverse=True)
    return orders[:limit]


def order_public(order):
    """ข้อมูลออเดอร์สำหรับหน้า success (มีลิงก์ดาวน์โหลด ไม่โชว์ path ไฟล์จริง)."""
    if not order:
        return None
    return {
        "id": order["id"],
        "status": order["status"],
        "amount_total": order["amount_total"],
        "currency": order["currency"],
        "email": order.get("email", ""),
        "items": [{"title": i["title"], "price": i["price"]} for i in order["items"]],
        "downloads": [
            {"token": d["token"], "title": d["title"],
             "remaining": max(0, d["max_downloads"] - d["count"]),
             "expires_at": d["expires_at"]}
            for d in order.get("downloads", [])
        ] if order["status"] == "paid" else [],
    }
