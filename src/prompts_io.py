"""อ่าน/เพิ่ม/ลบ แถวใน prompts.csv (ใช้โดย web UI และทีม agents)."""

import csv
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PROMPTS_PATH = os.path.join(PROJECT_ROOT, "prompts.csv")
FIELDS = ["title", "prompt", "negative", "seed", "tags"]


def read_prompts(path=PROMPTS_PATH):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            row = {k: (r.get(k) or "").strip() for k in FIELDS}
            if row.get("prompt"):
                rows.append(row)
        return rows


def _titles_lower(rows):
    return {r.get("title", "").strip().lower() for r in rows}


def append_prompts(new_rows, path=PROMPTS_PATH):
    """ต่อท้ายแถวใหม่ ข้ามอันที่ title ซ้ำ. คืนจำนวนที่เพิ่มจริง."""
    existing = read_prompts(path)
    seen = _titles_lower(existing)
    to_add = []
    for r in new_rows:
        title = (r.get("title") or "").strip()
        if not r.get("prompt") or (title and title.lower() in seen):
            continue
        seen.add(title.lower())
        to_add.append({k: (r.get(k) or "") for k in FIELDS})
    if not to_add:
        return 0

    file_exists = os.path.exists(path)
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(to_add)
    return len(to_add)


def delete_prompt(title, path=PROMPTS_PATH):
    """ลบแถวตาม title. คืน True ถ้าลบได้."""
    rows = read_prompts(path)
    kept = [r for r in rows if r.get("title", "").strip().lower() != title.strip().lower()]
    if len(kept) == len(rows):
        return False
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(kept)
    return True
