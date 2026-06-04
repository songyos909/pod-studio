"""อัปโหลดดีไซน์จาก output/catalog.csv ขึ้น Etsy หรือ Shopify.

ขั้นตอน:
  # 1) เตรียม credentials
  คัดลอก credentials.example.yaml -> credentials.yaml แล้วกรอกค่า

  # 2) (Etsy เท่านั้น) ยืนยันสิทธิ์ OAuth ครั้งแรก
  python src/upload_runner.py --platform etsy --auth

  # 3) เช็กว่าเชื่อมต่อได้ก่อนอัปจริง
  python src/upload_runner.py --platform shopify --validate
  python src/upload_runner.py --platform etsy --validate

  # 4) อัปโหลด (เริ่มเป็น draft ก่อนปลอดภัยกว่า)
  python src/upload_runner.py --platform shopify --limit 1
  python src/upload_runner.py --platform etsy --limit 1 --use-preview
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

import yaml  # noqa: E402

from upload import common  # noqa: E402
from upload import etsy as etsy_mod  # noqa: E402
from upload.etsy import EtsyClient, EtsyError  # noqa: E402
from upload.shopify import ShopifyClient, ShopifyError  # noqa: E402


def load_config(path="config.yaml"):
    with open(common.resolve(path), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pick_image(item, use_preview):
    if use_preview and item.get("preview_path"):
        return item["preview_path"]
    return item.get("image_path") or item.get("preview_path")


def main():
    ap = argparse.ArgumentParser(description="อัปโหลดดีไซน์ขึ้น Etsy/Shopify")
    ap.add_argument("--platform", choices=["etsy", "shopify"], help="แพลตฟอร์มปลายทาง")
    ap.add_argument("--auth", action="store_true", help="(Etsy) ยืนยันสิทธิ์ OAuth ครั้งแรก")
    ap.add_argument("--validate", action="store_true", help="แค่เช็กการเชื่อมต่อ/credentials")
    ap.add_argument("--limit", type=int, default=None, help="อัปไม่เกิน N รายการ")
    ap.add_argument("--force", action="store_true", help="อัปซ้ำแม้เคยอัปแล้ว")
    ap.add_argument("--use-preview", action="store_true", help="ใช้รูป preview .jpg แทนไฟล์ใหญ่")
    ap.add_argument("--state", choices=["draft", "active"], default=None, help="override สถานะ listing")
    ap.add_argument("--credentials", default="credentials.yaml")
    ap.add_argument("--catalog", default="output/catalog.csv")
    args = ap.parse_args()

    try:
        creds_all = common.load_credentials(args.credentials)
        config = load_config()
    except FileNotFoundError as e:
        print(f"[x] {e}")
        sys.exit(1)
    listing_cfg = config.get("listing", {})

    # ---- (Etsy) ยืนยันสิทธิ์ครั้งแรก ----
    if args.platform == "etsy" and args.auth:
        etsy_mod.run_oauth_flow(creds_all.get("etsy", {}))
        return
    if not args.platform:
        ap.error("ต้องระบุ --platform etsy|shopify")

    # ---- สร้าง client ----
    try:
        if args.platform == "shopify":
            c = creds_all.get("shopify", {})
            client = ShopifyClient(
                c.get("shop"), c.get("access_token"), c.get("api_version", "2024-10")
            )
        else:
            client = EtsyClient(creds_all.get("etsy", {}))
        name = client.test_connection()
        print(f"[ok] เชื่อมต่อ {args.platform} สำเร็จ: {name}")
    except (ShopifyError, EtsyError, FileNotFoundError) as e:
        print(f"[x] เชื่อมต่อไม่ผ่าน: {e}")
        sys.exit(1)

    if args.validate:
        return

    # ---- อัปโหลดจาก catalog ----
    items = common.load_catalog(args.catalog)
    state = common.UploadState()
    price = listing_cfg.get("price", 19.99)
    status = args.state or listing_cfg.get("state", "draft")
    tmpl = listing_cfg.get("description_template", "{title}")

    done = failed = skipped = 0
    for item in items:
        if args.limit is not None and done >= args.limit:
            break
        slug = item.get("slug") or item.get("title", "")
        if not args.force and state.is_uploaded(args.platform, slug):
            skipped += 1
            print(f"[=] ข้าม (อัปแล้ว): {item.get('title')}")
            continue

        img = common.resolve(pick_image(item, args.use_preview))
        desc = common.build_description(tmpl, item)
        try:
            if args.platform == "shopify":
                sc = listing_cfg.get("shopify", {})
                res = client.create_product(
                    title=item.get("title", slug), description=desc,
                    tags=item.get("tags", ""), price=price, image_path=img,
                    status=status, product_type=sc.get("product_type", ""),
                    vendor=sc.get("vendor", ""),
                )
                lid, url = res["id"], res.get("handle", "")
            else:
                ec = listing_cfg.get("etsy", {})
                lid = client.create_draft_listing(
                    title=item.get("title", slug), description=desc,
                    price=price, tags=item.get("tags", ""), listing_cfg=ec,
                )
                client.upload_listing_image(lid, img)
                url = f"listing {lid}"
            state.mark(args.platform, slug, lid, url)
            done += 1
            print(f"[ok] อัป: {item.get('title')} -> id={lid}")
        except Exception as e:
            failed += 1
            print(f"[x] ล้มเหลว: {item.get('title')} -> {e}")

    print(f"\nสรุป ({args.platform}): อัป {done} | ข้าม {skipped} | ล้มเหลว {failed}")
    if done:
        print("ดูสถานะการอัปได้ที่ output/upload_state.json")


if __name__ == "__main__":
    main()
