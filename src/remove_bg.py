"""เครื่องมือลบพื้นหลัง (background removal) ด้วย rembg -> ได้ PNG พื้นโปร่ง (RGBA).

ใช้เป็นโมดูล:
    from remove_bg import remove_background
    rgba_png_bytes = remove_background(png_bytes, model="u2net")

ใช้เป็นคำสั่ง (standalone):
    python src/remove_bg.py input.png                 # -> input_nobg.png
    python src/remove_bg.py input.png output.png
    python src/remove_bg.py --dir myfolder            # ทำทั้งโฟลเดอร์
    python src/remove_bg.py --dir myfolder --model isnet-general-use

หมายเหตุ: ครั้งแรกที่ใช้แต่ละโมเดล rembg จะดาวน์โหลดไฟล์โมเดล (~170MB) เก็บไว้ที่
~/.u2net อัตโนมัติ (ต้องต่อเน็ตครั้งแรก) หลังจากนั้นทำงาน offline ได้
"""

import argparse
import io
import os
import sys

# cache session ของแต่ละโมเดล (โหลดโมเดลครั้งเดียว)
_SESSIONS = {}


def _get_session(model):
    if model not in _SESSIONS:
        try:
            from rembg import new_session
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "ต้องติดตั้ง rembg ก่อน: pip install rembg onnxruntime"
            ) from e
        _SESSIONS[model] = new_session(model)
    return _SESSIONS[model]


def remove_background(image_bytes, model="u2net"):
    """คืน bytes ของ PNG (RGBA) ที่ลบพื้นหลังแล้ว."""
    from rembg import remove

    session = _get_session(model)
    # post_process_mask ช่วยให้ขอบ alpha คมขึ้น
    out = remove(image_bytes, session=session, post_process_mask=True)
    return out


def _process_file(in_path, out_path, model):
    with open(in_path, "rb") as f:
        data = f.read()
    result = remove_background(data, model=model)
    with open(out_path, "wb") as f:
        f.write(result)
    print(f"[ok] {in_path} -> {out_path}")


def _default_out(in_path):
    root, _ = os.path.splitext(in_path)
    return root + "_nobg.png"


def main():
    parser = argparse.ArgumentParser(description="ลบพื้นหลังรูปภาพด้วย rembg")
    parser.add_argument("input", nargs="?", help="ไฟล์ภาพต้นทาง")
    parser.add_argument("output", nargs="?", help="ไฟล์ปลายทาง (ไม่ใส่ = <ชื่อ>_nobg.png)")
    parser.add_argument("--dir", help="ทำทุกไฟล์รูปในโฟลเดอร์นี้")
    parser.add_argument("--model", default="u2net", help="โมเดล rembg")
    args = parser.parse_args()

    exts = (".png", ".jpg", ".jpeg", ".webp")
    if args.dir:
        files = [
            os.path.join(args.dir, f)
            for f in os.listdir(args.dir)
            if f.lower().endswith(exts) and "_nobg" not in f.lower()
        ]
        if not files:
            print(f"[!] ไม่พบไฟล์รูปใน {args.dir}")
            sys.exit(1)
        for fp in files:
            _process_file(fp, _default_out(fp), args.model)
        print(f"\nเสร็จ {len(files)} ไฟล์")
    elif args.input:
        out = args.output or _default_out(args.input)
        _process_file(args.input, out, args.model)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
