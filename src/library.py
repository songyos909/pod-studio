"""จัดการไฟล์ที่สร้างแล้ว: ลบดีไซน์ (ย้ายถังขยะ) + คลัง E-book (PDF).

ลบทุกอย่างเป็นแบบ "ย้ายไปถังขยะ" output/_trash/ เพื่อให้กู้คืนได้ ไม่ลบถาวร.
"""

import csv
import os
import re
import shutil
from datetime import datetime

import catalog as cat

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
CATALOG = os.path.join(OUTPUT_DIR, "catalog.csv")
BUNDLE_DIR = os.path.join(OUTPUT_DIR, "bundles")
TRASH_DIR = os.path.join(OUTPUT_DIR, "_trash")

_SAFE = re.compile(r"^[\w\-. ]+$", re.UNICODE)  # กัน path traversal


def _ts():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _read_catalog():
    if not os.path.exists(CATALOG):
        return []
    with open(CATALOG, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_catalog(rows):
    with open(CATALOG, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cat.CATALOG_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in cat.CATALOG_FIELDS})


# ---------------- ลบดีไซน์ในแกลเลอรี ----------------
def delete_design(slug):
    """ย้ายโฟลเดอร์ดีไซน์ slug ไปถังขยะ + เอาออกจาก catalog. คืน dict สรุป."""
    slug = (slug or "").strip()
    if not slug or not _SAFE.match(slug):
        raise ValueError("slug ไม่ถูกต้อง")

    rows = _read_catalog()
    matched = [r for r in rows if (r.get("slug") or "").strip() == slug]
    kept = [r for r in rows if (r.get("slug") or "").strip() != slug]

    # หาโฟลเดอร์ดีไซน์จาก image_path (output/<date>/<slug>/<file>)
    moved = []
    dirs = set()
    for r in matched:
        rel = (r.get("image_path") or r.get("preview_path") or "").strip()
        if rel:
            d = os.path.dirname(os.path.join(PROJECT_ROOT, rel))
            if os.path.isdir(d):
                dirs.add(os.path.abspath(d))

    os.makedirs(TRASH_DIR, exist_ok=True)
    for d in dirs:
        # กันย้ายออกนอก output
        if not d.startswith(os.path.abspath(OUTPUT_DIR)):
            continue
        dest = os.path.join(TRASH_DIR, f"{_ts()}_{os.path.basename(d)}")
        shutil.move(d, dest)
        moved.append(dest)

    if len(kept) != len(rows):
        _write_catalog(kept)

    return {"slug": slug, "moved": len(moved), "removed_rows": len(matched), "trash": TRASH_DIR}


# ---------------- คลัง E-book (PDF) ----------------
def _pdf_pages(path):
    """นับหน้า PDF แบบ best-effort (ไม่บังคับ dependency)."""
    try:
        from pypdf import PdfReader
        return len(PdfReader(path).pages)
    except Exception:
        pass
    try:
        # นับ /Type /Page จาก bytes (กันนับ /Type /Pages ที่เป็น node แม่)
        with open(path, "rb") as f:
            data = f.read()
        n = len(re.findall(rb"/Type\s*/Page(?![s])", data))
        return n or None
    except Exception:
        return None


THUMB_DIR = os.path.join(BUNDLE_DIR, "_thumbs")


def _bundle_thumb(path, name):
    """เรนเดอร์หน้าแรกของ PDF เป็นรูปย่อ (cache ใน _thumbs). คืน url หรือ ""."""
    try:
        import fitz  # pymupdf
    except Exception:
        return ""
    os.makedirs(THUMB_DIR, exist_ok=True)
    thumb = os.path.join(THUMB_DIR, os.path.splitext(name)[0] + ".jpg")
    try:
        # ใช้ cache ถ้ารูปย่อใหม่กว่าหรือเท่ากับ PDF
        if os.path.exists(thumb) and os.path.getmtime(thumb) >= os.path.getmtime(path):
            return "/output/bundles/_thumbs/" + os.path.basename(thumb)
        doc = fitz.open(path)
        if doc.page_count == 0:
            return ""
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(0.55, 0.55))
        pix.save(thumb, jpg_quality=80)
        doc.close()
        return "/output/bundles/_thumbs/" + os.path.basename(thumb)
    except Exception:
        return ""


def list_bundles():
    """รายการ PDF ใน output/bundles/ (ใหม่สุดก่อน)."""
    if not os.path.isdir(BUNDLE_DIR):
        return []
    items = []
    for name in os.listdir(BUNDLE_DIR):
        if not name.lower().endswith(".pdf"):
            continue
        path = os.path.join(BUNDLE_DIR, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        items.append({
            "name": name,
            "url": "/output/bundles/" + name,
            "size_mb": round(st.st_size / 1e6, 2),
            "mtime": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "pages": _pdf_pages(path),
            "preview": _bundle_thumb(path, name),
        })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items


def delete_bundle(name):
    """ย้าย PDF ไปถังขยะ. คืน dict สรุป."""
    name = (name or "").strip()
    if not name or not _SAFE.match(name) or not name.lower().endswith(".pdf"):
        raise ValueError("ชื่อไฟล์ไม่ถูกต้อง")
    path = os.path.join(BUNDLE_DIR, name)
    if not os.path.isfile(path):
        raise ValueError("ไม่พบไฟล์")
    os.makedirs(TRASH_DIR, exist_ok=True)
    dest = os.path.join(TRASH_DIR, f"{_ts()}_{name}")
    shutil.move(path, dest)
    return {"name": name, "trash": dest}
