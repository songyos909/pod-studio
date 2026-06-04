"""รวมดีไซน์จาก output/catalog.csv เป็นไฟล์ PDF พร้อมขาย (มีหน้าปก).

ใช้ได้ทั้งชุดภาพสีและหน้าหนังสือระบายสี (lineart).
รัน:  python src/bundle_pdf.py --title "My Coloring Book"
"""

import argparse
import csv
import os
import re
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CATALOG = os.path.join(PROJECT_ROOT, "output", "catalog.csv")
BUNDLE_DIR = os.path.join(PROJECT_ROOT, "output", "bundles")

# ขนาดหน้า @300dpi
PAGE_SIZES = {"A4": (2480, 3508), "letter": (2550, 3300)}

_FONT_CANDIDATES = [
    "C:/Windows/Fonts/tahoma.ttf",   # รองรับภาษาไทย
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]


def _resolve(p):
    return p if os.path.isabs(p) else os.path.join(PROJECT_ROOT, p)


def _font(size):
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _slugify(text):
    text = re.sub(r"\s+", "-", (text or "").strip().lower())
    text = re.sub(r"[^\w\-]", "", text, flags=re.UNICODE)
    return re.sub(r"-+", "-", text).strip("-") or "bundle"


def _read_catalog():
    if not os.path.exists(CATALOG):
        return []
    with open(CATALOG, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _unique_by_slug(rows):
    """เก็บรายการล่าสุดของแต่ละ slug (catalog ต่อท้ายเรื่อย ๆ)."""
    by_slug = {}
    for r in rows:
        s = (r.get("slug") or "").strip()
        if s:
            by_slug[s] = r  # อันหลังทับอันเก่า
    return by_slug


def _load_on_white(path, page):
    """โหลดภาพ -> วางกึ่งกลางหน้า (พื้นขาว) คงสัดส่วน."""
    img = Image.open(path)
    img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
    margin = int(min(page) * 0.06)
    box = (page[0] - 2 * margin, page[1] - 2 * margin)
    scale = min(box[0] / img.width, box[1] / img.height)
    new = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    fitted = img.resize(new, Image.LANCZOS)
    canvas = Image.new("RGB", page, (255, 255, 255))
    offset = ((page[0] - new[0]) // 2, (page[1] - new[1]) // 2)
    if fitted.mode == "RGBA":
        canvas.paste(fitted, offset, fitted)
    else:
        canvas.paste(fitted, offset)
    return canvas


def _cover(title, subtitle, page):
    canvas = Image.new("RGB", page, (255, 255, 255))
    draw = ImageDraw.Draw(canvas)
    # ตัดบรรทัดชื่อแบบง่าย ๆ
    f_title = _font(int(page[0] * 0.09))
    words = (title or "Collection").split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=f_title) > page[0] * 0.8 and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    lines.append(cur)
    y = int(page[1] * 0.32)
    for ln in lines:
        wln = draw.textlength(ln, font=f_title)
        draw.text(((page[0] - wln) / 2, y), ln, fill=(30, 30, 30), font=f_title)
        y += int(page[0] * 0.11)
    if subtitle:
        f_sub = _font(int(page[0] * 0.035))
        ws = draw.textlength(subtitle, font=f_sub)
        draw.text(((page[0] - ws) / 2, y + int(page[0] * 0.03)), subtitle,
                  fill=(120, 120, 120), font=f_sub)
    return canvas


def _draw_page_number(canvas, num, page):
    """วาดเลขหน้าที่กึ่งกลางด้านล่าง."""
    draw = ImageDraw.Draw(canvas)
    f = _font(int(page[0] * 0.022))
    text = str(num)
    w = draw.textlength(text, font=f)
    y = page[1] - int(page[1] * 0.045)
    draw.text(((page[0] - w) / 2, y), text, fill=(110, 110, 110), font=f)


def _resolve_items(items, slugs):
    """แปลง input เป็นลิสต์ path ที่เรียงลำดับแล้ว.

    items = [{"type":"slug"|"file","value":...}, ...] (ลำดับ = ลำดับหน้า)
    ถ้าไม่มี items แต่มี slugs (โหมดเดิม) ก็แปลงให้.
    ถ้าไม่มีทั้งคู่ = ใช้ทุกดีไซน์ใน catalog.
    คืน list ของ absolute path ที่มีจริง.
    """
    by_slug = _unique_by_slug(_read_catalog())
    if not items:
        if slugs:
            items = [{"type": "slug", "value": s} for s in slugs]
        else:
            items = [{"type": "slug", "value": s} for s in by_slug]

    paths = []
    for it in items:
        typ = (it.get("type") or "slug").strip()
        val = (it.get("value") or "").strip()
        if not val:
            continue
        if typ == "file":
            src = _resolve(val)
        else:
            r = by_slug.get(val)
            if not r:
                continue
            src = _resolve((r.get("image_path") or r.get("preview_path") or "").strip())
        if src and os.path.exists(src):
            paths.append(src)
    return paths


def build(slugs=None, title="My Collection", out_name=None, page_size="A4",
          cover=True, items=None, page_numbers=False):
    """สร้าง PDF.

    - items: ลิสต์เรียงลำดับ [{"type":"slug"|"file","value":...}] กำหนดลำดับหน้าเอง
    - slugs: (โหมดเดิม) รายชื่อ slug — ถ้าไม่มี items จะใช้อันนี้
    - page_numbers: True = พิมพ์เลขหน้าลงภาพ (หน้าเนื้อหาเริ่มที่ 1, ข้ามหน้าปก)
    """
    page = PAGE_SIZES.get(page_size, PAGE_SIZES["A4"])
    src_paths = _resolve_items(items, slugs)
    if not src_paths:
        raise ValueError("ไม่มีรูปให้รวม (ยังไม่ได้สร้างภาพ/อัปโหลด หรือ slug ไม่ตรง)")

    pages = []
    if cover:
        sub = f"{len(src_paths)} pages • {datetime.now().strftime('%Y-%m-%d')}"
        pages.append(_cover(title, sub, page))
    content_no = 0
    for src in src_paths:
        canvas = _load_on_white(src, page)
        content_no += 1
        if page_numbers:
            _draw_page_number(canvas, content_no, page)
        pages.append(canvas)

    if not pages:
        raise ValueError("ไม่พบไฟล์ภาพที่เลือก")

    os.makedirs(BUNDLE_DIR, exist_ok=True)
    name = (out_name or _slugify(title)) + ".pdf"
    out_path = os.path.join(BUNDLE_DIR, name)
    pages[0].save(out_path, "PDF", save_all=True, append_images=pages[1:], resolution=300.0)

    return {
        "pdf": out_path,
        "pdf_url": "/output/bundles/" + name,
        "pages": len(pages),
        "designs": len(src_paths),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="รวมดีไซน์เป็น PDF พร้อมขาย")
    ap.add_argument("--title", default="My Collection")
    ap.add_argument("--page-size", default="A4", choices=list(PAGE_SIZES))
    ap.add_argument("--slugs", nargs="*", help="ระบุ slug ที่ต้องการ (เว้น = ทั้งหมด)")
    ap.add_argument("--no-cover", action="store_true")
    args = ap.parse_args()
    res = build(slugs=args.slugs, title=args.title, page_size=args.page_size, cover=not args.no_cover)
    print(f"[ok] สร้าง PDF: {res['pdf']}  ({res['pages']} หน้า, {res['designs']} ดีไซน์)")
