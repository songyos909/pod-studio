"""ตัวสั่งงานหลัก: อ่าน prompts.csv -> generate ผ่าน ComfyUI -> เตรียมไฟล์ -> จัดเก็บ.

วิธีรัน (จากโฟลเดอร์โปรเจกต์):
    python src/run_batch.py                 # ทำทุกแถวใน prompts.csv
    python src/run_batch.py --limit 1       # ทดสอบ 1 ภาพ
    python src/run_batch.py --force         # สร้างใหม่แม้เคยทำแล้ว
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime

import yaml

# กัน UnicodeEncodeError ตอน print ชื่อดีไซน์ภาษาไทยบน console Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

# ให้ import โมดูลข้าง ๆ ได้ ไม่ว่าจะรันจากที่ไหน
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

from comfy_client import ComfyClient, ComfyUIError  # noqa: E402
import workflow as wf_mod  # noqa: E402
import postprocess as pp  # noqa: E402
import catalog as cat  # noqa: E402


def resolve(path):
    """แปลง path ให้อิงโฟลเดอร์โปรเจกต์ (ถ้าไม่ใช่ absolute)."""
    return path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)


def slugify(text, maxlen=60):
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^\w\-]", "", text, flags=re.UNICODE)  # \w รองรับภาษาไทย
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:maxlen] or "design"


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_prompts(path):
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for i, raw in enumerate(reader, start=1):
            row = {(k or "").strip(): (v or "").strip() for k, v in raw.items()}
            if not row.get("prompt"):
                continue
            row["_row"] = i
            rows.append(row)
    return rows


def design_exists(output_dir, slug):
    """เคยสร้าง slug นี้ไปแล้วหรือยัง (ดูทุกโฟลเดอร์วันที่)."""
    if not os.path.isdir(output_dir):
        return False
    for date_dir in os.listdir(output_dir):
        candidate = os.path.join(output_dir, date_dir, slug)
        if os.path.isdir(candidate):
            if any(fn.lower().endswith(".png") for fn in os.listdir(candidate)):
                return True
    return False


def main():
    parser = argparse.ArgumentParser(
        description="สร้างดีไซน์ Print-on-Demand เป็น batch ผ่าน ComfyUI"
    )
    parser.add_argument("--config", default="config.yaml", help="ไฟล์ config")
    parser.add_argument("--prompts", default=None, help="override path ของ prompts CSV")
    parser.add_argument("--limit", type=int, default=None, help="สร้างไม่เกิน N ดีไซน์")
    parser.add_argument("--force", action="store_true", help="สร้างใหม่แม้มีอยู่แล้ว")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--remove-bg", action="store_true", help="บังคับลบพื้นหลัง (override config)")
    g.add_argument("--keep-bg", action="store_true", help="บังคับไม่ลบพื้นหลัง (override config)")
    parser.add_argument("--coloring", action="store_true",
                        help="โหมดหนังสือระบายสี (ภาพลายเส้นขาว-ดำ, เก็บแยก slug -coloring)")
    parser.add_argument("--workflow", default=None, help="เลือก workflow: sdxl | flux2 (ดู config.workflows)")
    # override ค่า generation รายครั้ง (ไม่เขียนทับ config.yaml) — ใช้โดยหน้าเว็บ
    parser.add_argument("--checkpoint", default=None, help="override โมเดล (ckpt_name/unet_name)")
    parser.add_argument("--width", type=int, default=None, help="override ความกว้าง")
    parser.add_argument("--height", type=int, default=None, help="override ความสูง")
    parser.add_argument("--steps", type=int, default=None, help="override steps")
    parser.add_argument("--cfg", type=float, default=None, help="override cfg")
    parser.add_argument("--sampler", default=None, help="override sampler_name")
    parser.add_argument("--scheduler", default=None, help="override scheduler")
    parser.add_argument("--seed", type=int, default=None, help="override seed (-1 = สุ่ม)")
    parser.add_argument("--batch", type=int, default=None, help="override batch_size")
    args = parser.parse_args()

    config = load_config(resolve(args.config))
    comfy_cfg = config["comfyui"]
    gen_cfg = config["generation"]
    pp_cfg = config["postprocess"]
    up_cfg = config.get("upscale", {})
    col_cfg = config.get("coloring", {})

    # ---- เลือก workflow จากคลัง (sdxl/flux2/...) ----
    wf_name = args.workflow or gen_cfg.get("workflow") or "sdxl"
    workflows = config.get("workflows") or {}
    wf_def = workflows.get(wf_name)
    if not wf_def:
        print(f"[!] ไม่พบ workflow '{wf_name}' — มีให้เลือก: {', '.join(workflows) or '(ว่าง)'}")
        sys.exit(1)
    save_image_id = wf_def.get("save_image", "9")
    wf_defaults = wf_def.get("defaults") or {}
    wf_models = wf_def.get("models") or {}

    # ค่า override จาก CLI (เฉพาะที่ส่งมา) — เก็บแยกเพื่อคำนวณลำดับความสำคัญ
    overrides = {
        "checkpoint": args.checkpoint, "width": args.width, "height": args.height,
        "steps": args.steps, "cfg": args.cfg, "sampler_name": args.sampler,
        "scheduler": args.scheduler, "seed": args.seed, "batch_size": args.batch,
    }

    def eff(param):
        """ลำดับความสำคัญ: CLI override > ค่า default ของ workflow > generation block."""
        if overrides.get(param) is not None:
            return overrides[param]
        if param in wf_defaults:
            return wf_defaults[param]
        return gen_cfg.get(param)

    output_dir = resolve(config["output"]["dir"])
    catalog_path = os.path.join(output_dir, "catalog.csv")
    prompts_path = resolve(args.prompts or config.get("prompts_csv", "prompts.csv"))

    client = ComfyClient(
        host=comfy_cfg.get("host", "127.0.0.1"),
        port=comfy_cfg.get("port", 8188),
        client_id=comfy_cfg.get("client_id"),
        timeout_sec=comfy_cfg.get("timeout_sec", 600),
    )
    if not client.ping():
        print(f"[!] เชื่อมต่อ ComfyUI ไม่ได้ที่ {client.base}")
        print("    เปิด ComfyUI ให้รันอยู่ก่อน แล้วลองใหม่อีกครั้ง")
        sys.exit(1)

    base_wf = wf_mod.load_workflow(resolve(wf_def["path"]))
    print(f"[i] ใช้ workflow: {wf_name} ({wf_def.get('label', '')})")
    designs = read_prompts(prompts_path)
    if not designs:
        print(f"[!] ไม่พบ prompt ในไฟล์ {prompts_path}")
        sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")
    made = failed = skipped = 0

    for d in designs:
        if args.limit is not None and made >= args.limit:
            break

        title = d.get("title") or d["prompt"][:40]
        slug = slugify(title)
        if args.coloring:
            slug = slug + "-coloring"

        if not args.force and design_exists(output_dir, slug):
            skipped += 1
            print(f"[=] ข้าม (มีอยู่แล้ว): {title}")
            continue

        positive = d["prompt"]
        negative = d.get("negative") or gen_cfg.get("default_negative", "")
        if args.coloring:
            if col_cfg.get("positive_suffix"):
                positive = f"{positive}, {col_cfg['positive_suffix']}"
            if not d.get("negative") and col_cfg.get("negative"):
                negative = col_cfg["negative"]
        # seed: row > CLI/workflow/generation; -1 หรือว่าง = สุ่ม
        seed_in = d.get("seed")
        seed = int(seed_in) if seed_in not in (None, "") else eff("seed")
        if seed is None or int(seed) < 0:
            import random
            seed = random.randint(0, 2**63 - 1)
        else:
            seed = int(seed)
        used_seed = seed

        eff_width = eff("width")
        eff_height = eff("height")
        eff_checkpoint = (args.checkpoint or wf_models.get("checkpoint")
                          or gen_cfg.get("checkpoint"))
        values = {
            "positive": positive,
            "negative": negative,
            "width": eff_width, "height": eff_height,
            "batch_size": eff("batch_size") or 1,
            "seed": seed,
            "steps": eff("steps"), "cfg": eff("cfg"),
            "sampler_name": eff("sampler_name"), "scheduler": eff("scheduler"),
            "checkpoint": eff_checkpoint,
            "clip": wf_models.get("clip"),
            "vae": wf_models.get("vae"),
        }

        try:
            built = wf_mod.build_from_map(base_wf, wf_def, values)
            extra = ""
            if up_cfg.get("method") == "rtx":
                wf_mod.inject_rtx_upscale(
                    built, save_image_id,
                    node_id=up_cfg.get("node_id", "rtx_upscale"),
                    scale=up_cfg.get("scale", 4.0),
                    quality=up_cfg.get("quality", "ULTRA"),
                )
                extra = f"  RTX x{up_cfg.get('scale', 4.0)}"
            if args.coloring:
                extra += "  [ระบายสี/lineart]"
            print(f"[>] สร้าง: {title}  (seed={used_seed}){extra}")
            images = client.generate(built)
            if not images:
                raise ComfyUIError("ComfyUI ไม่คืนรูปภาพ (ตรวจ node SaveImage ใน workflow)")
        except Exception as e:
            failed += 1
            print(f"[x] ล้มเหลว: {title} -> {e}")
            continue

        design_dir = os.path.join(output_dir, today, slug)
        os.makedirs(design_dir, exist_ok=True)

        # ลบพื้นหลัง (ถ้าเปิดใช้) — โหลด rembg แบบ lazy เฉพาะตอนต้องใช้
        rmbg = pp_cfg.get("remove_background", False)
        if args.remove_bg:
            rmbg = True
        elif args.keep_bg:
            rmbg = False
        if args.coloring:
            rmbg = False  # ลายเส้นไม่ต้องลบพื้นหลัง
        rmbg_model = pp_cfg.get("rembg_model", "u2net")
        remover = None
        if rmbg:
            import remove_bg
            remover = lambda b: remove_bg.remove_background(b, model=rmbg_model)

        # โหมดระบายสีบังคับพื้นขาว
        pp_eff = dict(pp_cfg)
        if args.coloring:
            pp_eff["background"] = "white"

        main_path = None
        preview_path = None
        print_size = (eff_width, eff_height)
        for idx, img in enumerate(images):
            suffix = "" if idx == 0 else f"_{idx + 1}"
            raw = remover(img["data"]) if remover else img["data"]
            if args.coloring:
                raw = pp.to_lineart(raw, col_cfg.get("threshold"))
            print_bytes, size = pp.prepare_for_print(raw, pp_eff)
            path = os.path.join(design_dir, f"{slug}{suffix}.png")
            with open(path, "wb") as f:
                f.write(print_bytes)
            if idx == 0:
                main_path = path
                print_size = size
                if pp_cfg.get("save_preview_jpg", True):
                    preview_bytes = pp.make_preview(
                        raw, pp_cfg.get("preview_max_px", 1200)
                    )
                    preview_path = os.path.join(design_dir, f"{slug}_preview.jpg")
                    with open(preview_path, "wb") as f:
                        f.write(preview_bytes)

        meta = {
            "timestamp": cat.now_iso(),
            "title": title,
            "slug": slug,
            "prompt": positive,
            "negative": negative,
            "seed": used_seed,
            "checkpoint": eff_checkpoint or "(workflow default)",
            "workflow": wf_name,
            "width": eff_width,
            "height": eff_height,
            "print_width": print_size[0],
            "print_height": print_size[1],
            "dpi": pp_cfg.get("dpi", 300),
            "num_images": len(images),
            "image_path": os.path.relpath(main_path, PROJECT_ROOT),
            "preview_path": (
                os.path.relpath(preview_path, PROJECT_ROOT) if preview_path else ""
            ),
            "tags": d.get("tags", ""),
        }
        cat.write_metadata(design_dir, meta)
        cat.append_catalog(catalog_path, meta)
        made += 1
        print(f"[ok] เก็บไว้ที่ {design_dir}")

    print(f"\nสรุป: สำเร็จ {made} | ข้าม {skipped} | ล้มเหลว {failed}")
    if made:
        print(f"catalog: {catalog_path}")


if __name__ == "__main__":
    main()
