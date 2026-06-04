"""เตรียมไฟล์ภาพให้พร้อมขายแบบ Print-on-Demand ด้วย Pillow.

- อัปสเกล/ย่อให้ได้ความละเอียดเป้าหมาย (เช่น 4500x5400 @ 300dpi)
- คงสัดส่วนแล้ววางกลาง canvas (พื้นโปร่งหรือขาว) หรือยืดเต็มก็ได้
- ฝังค่า DPI ลงไฟล์ PNG
- สร้างไฟล์ JPG preview เล็ก ๆ สำหรับดู/อัปโหลดรายการสินค้า
"""

import io

from PIL import Image, ImageOps


def to_lineart(image_bytes, threshold=None):
    """แปลงภาพเป็นลายเส้นขาว-ดำสำหรับหนังสือระบายสี (เส้นดำ พื้นขาว).

    threshold = None  -> เกรย์สเกล + เพิ่มคอนทราสต์ (เส้นนุ่ม)
    threshold = 0-255 -> บังคับขาว-ดำคม (เหมาะกับลายเส้นล้วน)
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img = ImageOps.autocontrast(img, cutoff=1)
    if threshold is not None:
        t = int(threshold)
        img = img.point(lambda p: 255 if p >= t else 0, mode="L")
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _new_canvas(background, size):
    if background == "white":
        return Image.new("RGB", size, (255, 255, 255))
    return Image.new("RGBA", size, (0, 0, 0, 0))  # transparent


def prepare_for_print(image_bytes, cfg):
    """คืน (bytes ของ PNG พร้อมขาย, (width, height))."""
    img = Image.open(io.BytesIO(image_bytes))

    if not cfg.get("enabled", True):
        # คืนภาพเดิม (แปลงเป็น PNG เพื่อความสม่ำเสมอ)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue(), img.size

    target = (int(cfg["target_width"]), int(cfg["target_height"]))
    dpi = int(cfg.get("dpi", 300))
    background = cfg.get("background", "transparent")

    img = img.convert("RGBA" if background == "transparent" else "RGB")

    if cfg.get("keep_aspect", True):
        scale = min(target[0] / img.width, target[1] / img.height)
        new_size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
        fitted = img.resize(new_size, Image.LANCZOS)
        canvas = _new_canvas(background, target)
        offset = ((target[0] - fitted.width) // 2, (target[1] - fitted.height) // 2)
        if fitted.mode == "RGBA":
            canvas.paste(fitted, offset, fitted)  # ใช้ alpha เป็น mask
        else:
            canvas.paste(fitted, offset)
        out = canvas
    else:
        out = img.resize(target, Image.LANCZOS)

    buf = io.BytesIO()
    out.save(buf, format="PNG", dpi=(dpi, dpi))
    return buf.getvalue(), out.size


def make_preview(image_bytes, max_px=1200, bg=(255, 255, 255)):
    """ย่อภาพเป็น JPG เล็ก ๆ สำหรับ preview.

    ถ้าเป็นภาพพื้นโปร่ง (RGBA) จะวางบนพื้นขาวก่อน เพื่อให้ thumbnail สวยพร้อมลงขาย
    (JPG ไม่รองรับพื้นโปร่ง ถ้าไม่ทำจะกลายเป็นพื้นดำ)
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        canvas = Image.new("RGB", img.size, bg)
        canvas.paste(img, mask=img.getchannel("A"))
        img = canvas
    else:
        img = img.convert("RGB")
    img.thumbnail((int(max_px), int(max_px)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
