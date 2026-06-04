"""อ่าน/เขียน config.yaml โดย *คงคอมเมนต์และลำดับเดิมไว้* ด้วย ruamel.yaml.

ใช้โดยหน้า Setting บนเว็บ: ส่งค่าที่แก้มาเป็น dotted-path เช่น
    {"generation.width": 1024, "agents.provider": "ollama"}
แล้วเขียนกลับลงไฟล์โดยไม่ทำคอมเมนต์ภาษาไทยหาย
"""

import os

from ruamel.yaml import YAML

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.yaml")

# ฟิลด์ที่อนุญาตให้แก้ผ่านหน้าเว็บ (allow-list กันการเขียนค่ามั่ว/อันตราย)
# key = dotted path ใน config.yaml ; value = ชนิดข้อมูลที่ต้อง coerce
ALLOWED = {
    "comfyui.host": str,
    "comfyui.port": int,
    "comfyui.timeout_sec": int,
    "generation.workflow": str,
    "generation.checkpoint": str,
    "generation.width": int,
    "generation.height": int,
    "generation.batch_size": int,
    "generation.steps": int,
    "generation.cfg": float,
    "generation.sampler_name": str,
    "generation.scheduler": str,
    "generation.seed": int,
    "generation.default_negative": str,
    "upscale.method": str,
    "upscale.scale": float,
    "upscale.quality": str,
    "postprocess.enabled": bool,
    "postprocess.target_width": int,
    "postprocess.target_height": int,
    "postprocess.dpi": int,
    "postprocess.keep_aspect": bool,
    "postprocess.background": str,
    "postprocess.remove_background": bool,
    "postprocess.rembg_model": str,
    "postprocess.save_preview_jpg": bool,
    "postprocess.preview_max_px": int,
    "coloring.positive_suffix": str,
    "coloring.negative": str,
    "agents.provider": str,
    "agents.model": str,
    "agents.base_url": str,
    "agents.default_count": int,
    "agents.product": str,
    "site.shop_name": str,
    "site.currency": str,
    "site.price": int,
    "site.contact_email": str,
    "site.line_id": str,
    "site.gas_url": str,
    "site.intro": str,
}


def _yaml():
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # กันการตัดบรรทัดยาว (เช่น default_negative)
    return y


def load_doc():
    """โหลด config เป็น object แบบ round-trip (มีคอมเมนต์ติดมาด้วย)."""
    y = _yaml()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return y, y.load(f)


def read_config():
    """คืน config เป็น dict ธรรมดา (ใช้ส่งให้ frontend แสดงผล)."""
    import yaml

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _coerce(caster, value):
    if caster is bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on", "y")
    if caster is int:
        # เผื่อ frontend ส่ง "1024" หรือ 1024.0 มา
        return int(float(value))
    if caster is float:
        return float(value)
    return "" if value is None else str(value)


def update_config(updates: dict):
    """อัปเดตค่าตาม dotted-path (เฉพาะที่อยู่ใน ALLOWED) แล้วเขียนกลับไฟล์.

    คืน dict สรุป {"updated": [...], "skipped": [...]}.
    """
    y, doc = load_doc()
    updated, skipped = [], []

    for key, raw in updates.items():
        caster = ALLOWED.get(key)
        if caster is None:
            skipped.append(key)
            continue
        section, _, field = key.partition(".")
        node = doc.get(section)
        if node is None or field not in node:
            skipped.append(key)
            continue
        try:
            node[field] = _coerce(caster, raw)
            updated.append(key)
        except (ValueError, TypeError):
            skipped.append(key)

    if updated:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            y.dump(doc, f)

    return {"updated": updated, "skipped": skipped}
