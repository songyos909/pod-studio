"""ตัวช่วยที่ใช้ร่วมกันของการอัปโหลดทุกแพลตฟอร์ม.

- โหลด credentials.yaml (ความลับ) และ catalog.csv (รายการดีไซน์)
- จำสถานะว่าอัปโหลดอะไรไปแล้ว (output/upload_state.json) กันอัปซ้ำ
- หา path รูปจริงให้ถูกต้อง + ทำ description จาก template
"""

import csv
import json
import os
from datetime import datetime, timezone

import yaml

# โฟลเดอร์โปรเจกต์ = สองชั้นเหนือไฟล์นี้ (src/upload/common.py -> root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def resolve(path):
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def load_credentials(path="credentials.yaml"):
    full = resolve(path)
    if not os.path.exists(full):
        raise FileNotFoundError(
            f"ไม่พบไฟล์ credentials: {full}\n"
            "คัดลอก credentials.example.yaml -> credentials.yaml แล้วกรอกค่าก่อน"
        )
    with open(full, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_catalog(path="output/catalog.csv"):
    full = resolve(path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"ไม่พบ catalog: {full} — รัน run_batch.py สร้างดีไซน์ก่อน")
    with open(full, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_image_bytes(image_path):
    full = resolve(image_path)
    if not os.path.exists(full):
        raise FileNotFoundError(f"ไม่พบไฟล์ภาพ: {full}")
    with open(full, "rb") as f:
        return f.read()


def build_description(template, item):
    """แทนค่า {title} {tags} {prompt} ใน template."""
    if not template:
        return item.get("title", "")
    try:
        return template.format(
            title=item.get("title", ""),
            tags=item.get("tags", ""),
            prompt=item.get("prompt", ""),
        )
    except (KeyError, IndexError):
        return template


def _now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class UploadState:
    """จำว่าดีไซน์ไหนอัปโหลดขึ้นแพลตฟอร์มไหนแล้ว (กันอัปซ้ำ)."""

    def __init__(self, path="output/upload_state.json"):
        self.path = resolve(path)
        self.data = {}
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)

    def is_uploaded(self, platform, slug):
        return slug in self.data.get(platform, {})

    def mark(self, platform, slug, listing_id, url=""):
        self.data.setdefault(platform, {})[slug] = {
            "id": str(listing_id),
            "url": url,
            "at": _now(),
        }
        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
