"""อัปโหลดดีไซน์ขึ้น Etsy ผ่าน Open API v3 (OAuth2 + PKCE).

เตรียมก่อนใช้:
  1) สมัคร app: https://www.etsy.com/developers/your-apps -> ได้ keystring (API key)
  2) ตั้ง Callback URL ของ app ให้ตรงกับ redirect_uri (เช่น http://localhost:3456/callback)
  3) หา shop_id ของร้านตัวเอง
  4) กรอกใน credentials.yaml (etsy.keystring, etsy.shop_id, etsy.redirect_uri, etsy.scopes)
  5) รันยืนยันสิทธิ์ครั้งแรก:  python src/upload_runner.py --platform etsy --auth
เอกสาร: https://developers.etsy.com/documentation/reference
"""

import base64
import hashlib
import os
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

from . import common

TOKEN_PATH = common.resolve("etsy_token.json")
OAUTH_TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
OAUTH_CONNECT_URL = "https://www.etsy.com/oauth/connect"
API_BASE = "https://openapi.etsy.com/v3/application"


class EtsyError(Exception):
    pass


# ---------------- PKCE / OAuth ----------------
def _pkce_pair():
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def _save_token(tok):
    import json
    tok = dict(tok)
    tok["expires_at"] = time.time() + tok.get("expires_in", 3600) - 60
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=2)


def _load_token():
    import json
    if not os.path.exists(TOKEN_PATH):
        return None
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class _CallbackHandler(BaseHTTPRequestHandler):
    captured = {}

    def do_GET(self):
        qs = urllib.parse.urlparse(self.path).query
        params = dict(urllib.parse.parse_qsl(qs))
        _CallbackHandler.captured = params
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "เชื่อมต่อ Etsy สำเร็จ! กลับไปที่หน้าต่าง terminal ได้เลย"
        self.wfile.write(f"<html><body><h2>{msg}</h2></body></html>".encode("utf-8"))

    def log_message(self, *args):
        pass  # เงียบ


def run_oauth_flow(creds):
    """เปิดเบราว์เซอร์ให้ผู้ใช้อนุญาต แล้วแลก code เป็น token เก็บลง etsy_token.json."""
    keystring = creds.get("keystring")
    redirect_uri = creds.get("redirect_uri", "http://localhost:3456/callback")
    scopes = creds.get("scopes", "listings_r listings_w shops_r")
    if not keystring:
        raise EtsyError("ต้องตั้ง etsy.keystring ใน credentials.yaml")

    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    params = {
        "response_type": "code",
        "client_id": keystring,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{OAUTH_CONNECT_URL}?{urllib.parse.urlencode(params)}"

    parsed = urllib.parse.urlparse(redirect_uri)
    host, port = parsed.hostname or "localhost", parsed.port or 80

    print("กำลังเปิดเบราว์เซอร์เพื่อขออนุญาต Etsy...")
    print("ถ้าไม่เปิดอัตโนมัติ ก๊อปลิงก์นี้ไปเปิดเอง:\n", url)
    webbrowser.open(url)

    server = HTTPServer((host, port), _CallbackHandler)
    server.timeout = 300
    server.handle_request()  # รอ callback 1 ครั้ง
    captured = _CallbackHandler.captured

    if captured.get("state") != state:
        raise EtsyError("state ไม่ตรง (อาจถูกขัดจังหวะ) — ลองใหม่")
    code = captured.get("code")
    if not code:
        raise EtsyError(f"ไม่ได้ code กลับมา: {captured}")

    resp = requests.post(OAUTH_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": keystring,
        "redirect_uri": redirect_uri,
        "code": code,
        "code_verifier": verifier,
    }, timeout=30)
    if resp.status_code != 200:
        raise EtsyError(f"แลก token ไม่สำเร็จ ({resp.status_code}): {resp.text}")
    _save_token(resp.json())
    print(f"[ok] บันทึก token แล้วที่ {TOKEN_PATH}")


def _valid_access_token(creds):
    tok = _load_token()
    if not tok:
        raise EtsyError("ยังไม่มี token — รัน: python src/upload_runner.py --platform etsy --auth")
    if time.time() < tok.get("expires_at", 0):
        return tok["access_token"]
    # หมดอายุ -> refresh
    resp = requests.post(OAUTH_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": creds.get("keystring"),
        "refresh_token": tok["refresh_token"],
    }, timeout=30)
    if resp.status_code != 200:
        raise EtsyError(f"refresh token ไม่สำเร็จ ({resp.status_code}): {resp.text} — รัน --auth ใหม่")
    new = resp.json()
    new.setdefault("refresh_token", tok["refresh_token"])
    _save_token(new)
    return new["access_token"]


# ---------------- API client ----------------
class EtsyClient:
    def __init__(self, creds):
        self.keystring = creds.get("keystring")
        self.shop_id = str(creds.get("shop_id", "")).strip()
        if not self.keystring or not self.shop_id:
            raise EtsyError("ต้องตั้ง etsy.keystring และ etsy.shop_id ใน credentials.yaml")
        self.creds = creds

    def _headers(self, extra=None):
        h = {
            "x-api-key": self.keystring,
            "Authorization": f"Bearer {_valid_access_token(self.creds)}",
        }
        if extra:
            h.update(extra)
        return h

    def test_connection(self):
        r = requests.get(f"{API_BASE}/shops/{self.shop_id}", headers=self._headers(), timeout=30)
        if r.status_code != 200:
            raise EtsyError(f"เชื่อมต่อ Etsy ไม่ผ่าน ({r.status_code}): {r.text}")
        return r.json().get("shop_name", "(unknown)")

    def create_draft_listing(self, title, description, price, tags, listing_cfg):
        """สร้าง draft listing คืน listing_id."""
        # Etsy: title <=140 ตัว, tags <=13 อัน อันละ <=20 ตัว
        tag_list = [t.strip()[:20] for t in (tags or "").split(",") if t.strip()][:13]
        data = {
            "quantity": listing_cfg.get("quantity", 999),
            "title": title[:140],
            "description": description,
            "price": f"{float(price):.2f}",
            "who_made": listing_cfg.get("who_made", "i_did"),
            "when_made": listing_cfg.get("when_made", "made_to_order"),
            "taxonomy_id": listing_cfg.get("taxonomy_id", 1),
            "type": listing_cfg.get("type", "physical"),
        }
        if tag_list:
            data["tags"] = ",".join(tag_list)
        if listing_cfg.get("shipping_profile_id"):
            data["shipping_profile_id"] = listing_cfg["shipping_profile_id"]

        r = requests.post(
            f"{API_BASE}/shops/{self.shop_id}/listings",
            headers=self._headers({"Content-Type": "application/x-www-form-urlencoded"}),
            data=data,
            timeout=60,
        )
        if r.status_code not in (200, 201):
            raise EtsyError(f"สร้าง draft listing ไม่สำเร็จ ({r.status_code}): {r.text}")
        return r.json()["listing_id"]

    def upload_listing_image(self, listing_id, image_path):
        with open(image_path, "rb") as f:
            files = {"image": (os.path.basename(image_path), f, "image/png")}
            r = requests.post(
                f"{API_BASE}/shops/{self.shop_id}/listings/{listing_id}/images",
                headers=self._headers(),  # อย่าตั้ง Content-Type เอง ให้ requests จัดการ multipart
                files=files,
                timeout=180,
            )
        if r.status_code not in (200, 201):
            raise EtsyError(f"อัปโหลดรูปไม่สำเร็จ ({r.status_code}): {r.text}")
        return r.json().get("listing_image_id")
