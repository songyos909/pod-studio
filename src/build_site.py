"""สร้างไฟล์ static ของเว็บร้าน (docs/) จาก output/catalog.csv.

- เขียน docs/data.json = { shop: {...}, products: [...] }
- ก๊อปรูป preview ของแต่ละดีไซน์ไป docs/previews/<slug>.jpg
- docs/index.html + docs/assets/* เป็นไฟล์ static ที่เขียนไว้แล้ว (เอาขึ้น GitHub Pages ได้เลย)

รัน:  python src/build_site.py
"""

import csv
import json
import os
import shutil

import yaml

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
PREVIEWS_DIR = os.path.join(DOCS_DIR, "previews")
CATALOG = os.path.join(PROJECT_ROOT, "output", "catalog.csv")


def _resolve(path):
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def _load_config():
    with open(os.path.join(PROJECT_ROOT, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _read_catalog():
    if not os.path.exists(CATALOG):
        return []
    with open(CATALOG, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build():
    """สร้างเว็บร้าน. คืน dict สรุปผล."""
    cfg = _load_config()
    site = cfg.get("site", {})
    default_price = site.get("price", 290)

    os.makedirs(PREVIEWS_DIR, exist_ok=True)
    rows = _read_catalog()

    products = []
    seen = set()
    for r in rows:
        slug = (r.get("slug") or "").strip()
        if not slug or slug in seen:
            continue  # กันสินค้าซ้ำ (ใช้รายการล่าสุดของแต่ละ slug)
        # หา preview ที่จะก๊อป (preview_path > image_path)
        src_rel = (r.get("preview_path") or r.get("image_path") or "").strip()
        if not src_rel:
            continue
        src = _resolve(src_rel)
        if not os.path.exists(src):
            continue
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        dest_name = f"{slug}{ext}"
        shutil.copyfile(src, os.path.join(PREVIEWS_DIR, dest_name))
        seen.add(slug)
        products.append({
            "title": r.get("title") or slug,
            "slug": slug,
            "price": default_price,
            "tags": r.get("tags", ""),
            "image": f"previews/{dest_name}",
        })

    data = {
        "shop": {
            "name": site.get("shop_name", "My POD Store"),
            "currency": site.get("currency", "THB"),
            "intro": site.get("intro", ""),
            "contact_email": site.get("contact_email", ""),
            "line_id": site.get("line_id", ""),
            "gas_url": site.get("gas_url", ""),
        },
        "products": products,
    }
    with open(os.path.join(DOCS_DIR, "data.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return {"products": len(products), "gas_configured": bool(site.get("gas_url")), "docs": DOCS_DIR}


if __name__ == "__main__":
    result = build()
    print(f"[ok] สร้างเว็บร้านแล้ว: {result['products']} สินค้า -> {result['docs']}")
    if not result["gas_configured"]:
        print("    (ยังไม่ได้ตั้ง site.gas_url — ฟอร์มสั่งซื้อจะใช้อีเมลแทนไปก่อน)")
