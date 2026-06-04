"""อัปโหลดดีไซน์ขึ้น Shopify ผ่าน Admin REST API.

เตรียมก่อนใช้:
  1) Shopify Admin -> Settings -> Apps and sales channels -> Develop apps
  2) สร้าง custom app, ขอ scope: write_products, read_products
  3) Install app แล้วก๊อป Admin API access token (ขึ้นต้น shpat_...)
  4) ใส่ใน credentials.yaml: shopify.shop, shopify.access_token, shopify.api_version
เอกสาร: https://shopify.dev/docs/api/admin-rest/latest/resources/product
"""

import base64
import os

import requests


class ShopifyError(Exception):
    pass


class ShopifyClient:
    def __init__(self, shop, access_token, api_version="2024-10"):
        if not shop or not access_token:
            raise ShopifyError("ต้องตั้ง shopify.shop และ shopify.access_token ใน credentials.yaml")
        # รับได้ทั้ง "myshop" และ "myshop.myshopify.com"
        host = shop if shop.endswith(".myshopify.com") else f"{shop}.myshopify.com"
        self.base = f"https://{host}/admin/api/{api_version}"
        self.headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

    def test_connection(self):
        """คืนชื่อร้านถ้าเชื่อมต่อ + token ถูกต้อง."""
        r = requests.get(f"{self.base}/shop.json", headers=self.headers, timeout=30)
        if r.status_code != 200:
            raise ShopifyError(f"เชื่อมต่อ Shopify ไม่ผ่าน ({r.status_code}): {r.text}")
        return r.json().get("shop", {}).get("name", "(unknown)")

    def create_product(self, title, description, tags, price, image_path,
                       status="draft", product_type="", vendor=""):
        """สร้าง product + แนบรูป (รูปส่งเป็น base64 attachment ในคำขอเดียว)."""
        with open(image_path, "rb") as f:
            attachment = base64.b64encode(f.read()).decode("ascii")

        product = {
            "title": title,
            "body_html": (description or "").replace("\n", "<br>"),
            "status": status,                 # draft | active
            "images": [{
                "attachment": attachment,
                "filename": os.path.basename(image_path),
            }],
            "variants": [{"price": f"{float(price):.2f}"}],
        }
        if tags:
            product["tags"] = tags
        if product_type:
            product["product_type"] = product_type
        if vendor:
            product["vendor"] = vendor

        r = requests.post(
            f"{self.base}/products.json",
            headers=self.headers,
            json={"product": product},
            timeout=120,
        )
        if r.status_code not in (200, 201):
            raise ShopifyError(f"สร้าง product ไม่สำเร็จ ({r.status_code}): {r.text}")

        p = r.json()["product"]
        return {"id": p["id"], "handle": p.get("handle", ""), "admin": p.get("admin_graphql_api_id", "")}
