"""เส้นทางฝั่งลูกค้า + การส่งไฟล์: /store/*  (รวมเข้า FastAPI app หลัก).

flow: ลูกค้าเลือกสินค้า -> /store/api/checkout สร้างออเดอร์+Stripe session ->
ไปหน้าจ่ายของ Stripe (หรือ mock) -> กลับมา /store/success -> ยืนยันจ่าย -> ได้ลิงก์ดาวน์โหลด.
"""

import os

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from . import orders, payments, products

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOREFRONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "webapp", "storefront")

router = APIRouter()


def _cfg():
    import yaml
    try:
        with open(os.path.join(PROJECT_ROOT, "config.yaml"), "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _store_cfg():
    c = _cfg()
    store = c.get("store", {}) or {}
    site = c.get("site", {}) or {}
    return {
        "shop_name": store.get("shop_name") or site.get("shop_name", "My Digital Store"),
        "currency": (store.get("currency") or "thb").lower(),
        "intro": store.get("intro") or site.get("intro", ""),
        "expiry_days": int(store.get("download_expiry_days", orders.DEFAULT_EXPIRY_DAYS)),
        "max_downloads": int(store.get("max_downloads", orders.DEFAULT_MAX_DOWNLOADS)),
    }


def _base_url(request: Request):
    # ใช้ host จาก request เพื่อรองรับทั้ง localhost และ tunnel ภายหลัง
    return str(request.base_url).rstrip("/")


# ---------------- หน้าเว็บ (HTML) ----------------
@router.get("/store", response_class=HTMLResponse)
def storefront():
    return FileResponse(os.path.join(STOREFRONT_DIR, "index.html"))


@router.get("/store/success", response_class=HTMLResponse)
def success_page():
    return FileResponse(os.path.join(STOREFRONT_DIR, "success.html"))


@router.get("/store/mock-pay", response_class=HTMLResponse)
def mock_pay_page():
    return FileResponse(os.path.join(STOREFRONT_DIR, "mock-pay.html"))


# ---------------- API ----------------
@router.get("/store/api/info")
def store_info():
    sc = _store_cfg()
    return {"shop_name": sc["shop_name"], "currency": sc["currency"],
            "intro": sc["intro"], "mode": payments.mode()}


@router.get("/store/api/products")
def api_products():
    return {"products": products.public_products()}


class CheckoutReq(BaseModel):
    items: list[str]  # รายการ product id


@router.post("/store/api/checkout")
def checkout(req: CheckoutReq, request: Request):
    chosen = [products.get_product(pid) for pid in (req.items or [])]
    chosen = [p for p in chosen if p and p.get("active")]
    if not chosen:
        return JSONResponse({"error": "ไม่พบสินค้าที่เลือก"}, status_code=400)
    sc = _store_cfg()
    currency = chosen[0].get("currency") or sc["currency"]
    order = orders.create_order(chosen, currency=currency)
    base = _base_url(request)
    try:
        sess = payments.create_checkout_session(
            order, success_url=f"{base}/store/success",
            cancel_url=f"{base}/store", base_url=base)
    except Exception as e:
        return JSONResponse({"error": f"สร้างการชำระเงินไม่สำเร็จ: {e}"}, status_code=400)
    orders.set_session(order["id"], sess["session_id"])
    return {"url": sess["url"], "mode": sess["mode"], "order_id": order["id"]}


@router.get("/store/api/order")
def api_order(session_id: str):
    """ใช้โดยหน้า success — ยืนยันการจ่าย (idempotent) แล้วคืนลิงก์ดาวน์โหลด."""
    order = orders.get_by_session(session_id)
    if not order:
        return JSONResponse({"error": "ไม่พบคำสั่งซื้อ"}, status_code=404)
    sc = _store_cfg()
    if order["status"] != "paid":
        # ยืนยันกับ Stripe (เผื่อ webhook ยังไม่มา) — mock จะคืน paid เสมอ
        try:
            info = payments.retrieve_session(session_id)
        except Exception as e:
            return JSONResponse({"error": f"ตรวจสอบการชำระเงินไม่สำเร็จ: {e}"}, status_code=400)
        if info.get("payment_status") == "paid":
            orders.mark_paid(order["id"], email=info.get("customer_email", ""),
                             amount_total=info.get("amount_total"),
                             expiry_days=sc["expiry_days"], max_downloads=sc["max_downloads"])
            order = orders.get_order(order["id"])
    return orders.order_public(order)


@router.post("/store/webhook")
async def webhook(request: Request):
    """รับ event จาก Stripe — checkout.session.completed -> ส่งของ."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = payments.verify_webhook(payload, sig)
    except Exception as e:
        return JSONResponse({"error": f"webhook ไม่ถูกต้อง: {e}"}, status_code=400)
    if event["type"] == "checkout.session.completed":
        s = event["data"]["object"]
        oid = (s.get("metadata") or {}).get("order_id") or s.get("client_reference_id")
        if oid:
            sc = _store_cfg()
            email = (s.get("customer_details") or {}).get("email", "")
            orders.mark_paid(oid, email=email, amount_total=s.get("amount_total"),
                             expiry_days=sc["expiry_days"], max_downloads=sc["max_downloads"])
    return {"received": True}


# ---------------- mock checkout (เฉพาะโหมด mock) ----------------
@router.post("/store/mock-pay/confirm")
def mock_confirm(order_id: str):
    if payments.mode() != "mock":
        return JSONResponse({"error": "ใช้ได้เฉพาะโหมดทดสอบ (ไม่มีคีย์ Stripe)"}, status_code=400)
    order = orders.get_order(order_id)
    if not order:
        return JSONResponse({"error": "ไม่พบคำสั่งซื้อ"}, status_code=404)
    sc = _store_cfg()
    orders.mark_paid(order_id, email="test@localhost",
                     expiry_days=sc["expiry_days"], max_downloads=sc["max_downloads"])
    return {"ok": True, "session_id": order.get("session_id") or ("mock_" + order_id)}


# ---------------- ดาวน์โหลดไฟล์ (ต้องมีโทเคนที่จ่ายแล้ว) ----------------
@router.get("/store/download/{token}")
def download(token: str):
    ok, info, err = orders.use_token(token)
    if not ok:
        return JSONResponse({"error": err}, status_code=403)
    path = os.path.join(PROJECT_ROOT, info["file"])
    if not os.path.isfile(path):
        return JSONResponse({"error": "ไฟล์สินค้าหาย — ติดต่อร้าน"}, status_code=404)
    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="application/octet-stream")
