"""โหลด ComfyUI workflow (API format) แล้วแทนค่า prompt / seed / ขนาดภาพ."""

import copy
import json
import random

MAX_SEED = 2**63 - 1


def load_workflow(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _set_input(workflow, node_id, key, value):
    node = workflow.get(node_id)
    if node is None:
        raise KeyError(
            f"ไม่พบ node '{node_id}' ใน workflow — ตรวจ workflow.nodes ใน config.yaml ให้ตรงกับไฟล์ workflow"
        )
    node.setdefault("inputs", {})[key] = value


def build_workflow(base_workflow, nodes, gen_cfg, positive, negative, seed=None):
    """คืน (workflow ที่แทนค่าแล้ว, seed ที่ใช้จริง)."""
    wf = copy.deepcopy(base_workflow)

    _set_input(wf, nodes["positive_prompt"], "text", positive)
    _set_input(wf, nodes["negative_prompt"], "text", negative)

    _set_input(wf, nodes["latent"], "width", gen_cfg["width"])
    _set_input(wf, nodes["latent"], "height", gen_cfg["height"])
    _set_input(wf, nodes["latent"], "batch_size", gen_cfg.get("batch_size", 1))

    # seed: ใช้ค่าจาก argument > config; ถ้า <0 หรือไม่ระบุ = สุ่ม
    if seed is None:
        seed = gen_cfg.get("seed", -1)
    if seed is None or seed < 0:
        seed = random.randint(0, MAX_SEED)
    _set_input(wf, nodes["sampler"], "seed", seed)

    for key in ("steps", "cfg", "sampler_name", "scheduler"):
        if gen_cfg.get(key) is not None:
            _set_input(wf, nodes["sampler"], key, gen_cfg[key])

    ckpt = gen_cfg.get("checkpoint")
    if ckpt:
        _set_input(wf, nodes["checkpoint"], "ckpt_name", ckpt)

    return wf, seed


# ---------- ตัวสร้างแบบยืดหยุ่น (รองรับหลาย workflow ผ่าน param map) ----------
# param ที่ถ้าค่าว่าง "" จะข้าม (ปล่อยให้ใช้ค่าในไฟล์ workflow) — พวกชื่อโมเดล
_SKIP_IF_EMPTY = {"checkpoint", "clip", "vae"}


def build_from_map(base_workflow, wf_def, values):
    """สร้าง workflow โดยเขียนค่าใน `values` ลง node ตาม `wf_def['map']`.

    map: { param: [[node_id, input_key], ...] }  (1 param ไปได้หลาย node)
    values: { positive, negative, width, height, batch_size, seed, steps, cfg,
              sampler_name, scheduler, checkpoint, clip, vae, ... }
    - ข้าม negative ถ้า workflow ไม่รองรับ (wf_def['negative'] = false)
    - ข้ามค่า None ทุกตัว, ข้าม "" เฉพาะชื่อโมเดล (ใช้ค่าในไฟล์แทน)
    """
    wf = copy.deepcopy(base_workflow)
    mapping = wf_def.get("map", {})
    supports_neg = wf_def.get("negative", False)

    for param, targets in mapping.items():
        if param == "negative" and not supports_neg:
            continue
        if param not in values:
            continue
        val = values[param]
        if val is None:
            continue
        if param in _SKIP_IF_EMPTY and val == "":
            continue
        for node_id, key in targets:
            _set_input(wf, node_id, key, val)
    return wf


def inject_rtx_upscale(workflow, save_image_node_id, node_id="rtx_upscale",
                       scale=4.0, quality="ULTRA"):
    """แทรก node RTXVideoSuperResolution คั่นก่อน SaveImage เพื่ออัปสเกลด้วย NVIDIA RTX.

    เอาแหล่งภาพเดิมที่ SaveImage ดึงอยู่ (เช่น VAEDecode) มาผ่าน RTX ก่อน
    แล้วชี้ SaveImage ให้รับภาพจาก RTX แทน. รองรับ scale 1.0-4.0.
    """
    save_node = workflow.get(save_image_node_id)
    if save_node is None:
        raise KeyError(f"ไม่พบ SaveImage node '{save_image_node_id}' สำหรับแทรก RTX upscale")
    source = save_node["inputs"]["images"]
    scale = max(1.0, min(4.0, float(scale)))  # RTX รองรับ 1.0-4.0
    workflow[node_id] = {
        "class_type": "RTXVideoSuperResolution",
        "inputs": {
            "images": source,
            "resize_type": "scale by multiplier",
            "resize_type.scale": scale,  # คีย์ sub-input ของ dynamic combo
            "quality": quality,
        },
    }
    save_node["inputs"]["images"] = [node_id, 0]
    return workflow
