"""เขียน metadata ต่อหนึ่งดีไซน์ และรวมทุกดีไซน์ลง catalog.csv."""

import csv
import json
import os
from datetime import datetime, timezone

# คอลัมน์ใน catalog.csv (ใช้กรอกข้อมูลตอนอัปโหลดขายภายหลังได้)
CATALOG_FIELDS = [
    "timestamp", "title", "slug", "prompt", "negative",
    "seed", "checkpoint", "width", "height",
    "print_width", "print_height", "dpi",
    "num_images", "image_path", "preview_path", "tags",
]


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_metadata(design_dir, meta):
    path = os.path.join(design_dir, "metadata.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return path


def append_catalog(catalog_path, meta):
    """ต่อท้าย 1 แถวลง catalog.csv (สร้าง header ให้ถ้ายังไม่มีไฟล์)."""
    os.makedirs(os.path.dirname(catalog_path), exist_ok=True)
    exists = os.path.exists(catalog_path)
    row = {k: meta.get(k, "") for k in CATALOG_FIELDS}
    # utf-8-sig เพื่อให้ Excel อ่านภาษาไทยได้ถูกต้อง
    with open(catalog_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CATALOG_FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
