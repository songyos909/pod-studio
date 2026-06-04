"""คุยกับ Stripe Checkout + โหมดทดสอบ (mock) สำหรับรันบน PC โดยยังไม่ต้องมีคีย์.

โหมด:
- live  : มี secret key ขึ้นต้น sk_live  -> เก็บเงินจริง
- test  : มี secret key ขึ้นต้น sk_test  -> Stripe test mode (บัตรทดสอบ 4242...)
- mock  : ไม่มีคีย์เลย -> ใช้หน้า mock-pay ในเครื่อง จำลองการจ่าย (ไว้ทดสอบ flow)

คีย์อ่านจาก env (STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / STRIPE_PUBLISHABLE_KEY)
หรือ credentials.yaml > stripe: {secret_key, publishable_key, webhook_secret}
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# สกุลเงินที่ไม่มีหน่วยย่อย (จ่ายเป็นจำนวนเต็ม ไม่ต้อง ×100)
ZERO_DECIMAL = {"jpy", "krw", "vnd", "clp"}


def _creds():
    try:
        from upload import common
        return (common.load_credentials() or {}).get("stripe", {}) or {}
    except Exception:
        return {}


def get_keys():
    c = _creds()
    return {
        "secret_key": os.environ.get("STRIPE_SECRET_KEY") or c.get("secret_key") or "",
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY") or c.get("publishable_key") or "",
        "webhook_secret": os.environ.get("STRIPE_WEBHOOK_SECRET") or c.get("webhook_secret") or "",
    }


def mode():
    sk = get_keys()["secret_key"]
    if not sk:
        return "mock"
    if sk.startswith("sk_live"):
        return "live"
    return "test"


def _stripe():
    import stripe
    stripe.api_key = get_keys()["secret_key"]
    return stripe


def _unit_amount(price, currency):
    return int(price) if currency.lower() in ZERO_DECIMAL else int(price) * 100


def create_checkout_session(order, success_url, cancel_url, base_url):
    """สร้าง checkout session. คืน {url, session_id, mode}."""
    m = mode()
    if m == "mock":
        # โหมดจำลอง: ส่งไปหน้า mock-pay ในเครื่อง (ไม่เก็บเงินจริง)
        return {
            "url": f"{base_url}/store/mock-pay?order_id={order['id']}",
            "session_id": "mock_" + order["id"],
            "mode": "mock",
        }

    stripe = _stripe()
    currency = (order.get("currency") or "thb").lower()
    line_items = [{
        "price_data": {
            "currency": currency,
            "product_data": {"name": it["title"] or "Digital product"},
            "unit_amount": _unit_amount(it["price"], currency),
        },
        "quantity": 1,
    } for it in order["items"]]

    pmt = ["card"]
    if currency == "thb":
        pmt.append("promptpay")  # Stripe รองรับ PromptPay สำหรับ THB

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        payment_method_types=pmt,
        success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        client_reference_id=order["id"],
        metadata={"order_id": order["id"]},
    )
    return {"url": session.url, "session_id": session.id, "mode": m}


def retrieve_session(session_id):
    """ดึงข้อมูล session (ใช้ตอน success page ยืนยันว่าจ่ายจริง)."""
    if mode() == "mock" or (session_id or "").startswith("mock_"):
        return {"payment_status": "paid", "customer_email": "", "amount_total": None, "mock": True}
    stripe = _stripe()
    s = stripe.checkout.Session.retrieve(session_id)
    return {
        "payment_status": s.get("payment_status"),
        "customer_email": (s.get("customer_details") or {}).get("email", "") or s.get("customer_email", ""),
        "amount_total": s.get("amount_total"),
        "order_id": (s.get("metadata") or {}).get("order_id") or s.get("client_reference_id"),
    }


def verify_webhook(payload, sig_header):
    """ตรวจลายเซ็น webhook แล้วคืน event. raise ถ้าไม่ผ่าน."""
    secret = get_keys()["webhook_secret"]
    stripe = _stripe()
    if not secret:
        raise ValueError("ยังไม่ได้ตั้ง STRIPE_WEBHOOK_SECRET")
    return stripe.Webhook.construct_event(payload, sig_header, secret)
