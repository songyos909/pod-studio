"""Web UI สำหรับคุมทั้งระบบ POD: ทีม AI -> prompts -> generate -> gallery -> upload.

รัน:  python src/webapp/server.py
แล้วเปิดเบราว์เซอร์ที่ http://127.0.0.1:8500
"""

import os
import subprocess
import sys
import threading
import uuid

import yaml
from fastapi import FastAPI, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")
sys.path.insert(0, SRC_DIR)

import build_site  # noqa: E402
import bundle_pdf  # noqa: E402
import config_io  # noqa: E402
import library  # noqa: E402
import prompts_io  # noqa: E402
from store import orders as store_orders  # noqa: E402
from store import payments as store_payments  # noqa: E402
from store import products as store_products  # noqa: E402
from store import web as store_web  # noqa: E402
from agents import team as agent_team  # noqa: E402
from agents.base import AgentError  # noqa: E402

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)


def load_config():
    with open(os.path.join(PROJECT_ROOT, "config.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------- job manager (สำหรับงานที่รันนาน) ----------------
JOBS = {}


def _run_job(job_id, cmd):
    job = JOBS[job_id]
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.Popen(
            cmd, cwd=PROJECT_ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        for line in proc.stdout:
            job["log"].append(line.rstrip("\n"))
        proc.wait()
        job["returncode"] = proc.returncode
        job["status"] = "done" if proc.returncode == 0 else "error"
    except Exception as e:  # pragma: no cover
        job["log"].append(f"[x] {e}")
        job["status"] = "error"
        job["returncode"] = -1


def start_job(cmd):
    job_id = uuid.uuid4().hex[:8]
    JOBS[job_id] = {"status": "running", "log": [], "returncode": None}
    threading.Thread(target=_run_job, args=(job_id, cmd), daemon=True).start()
    return job_id


# ---------------- request models ----------------
class BrainstormReq(BaseModel):
    brief: str
    count: int | None = None
    product: str | None = None
    options: dict | None = None


class AddPromptsReq(BaseModel):
    rows: list[dict]


class DeletePromptReq(BaseModel):
    title: str


class GenerateReq(BaseModel):
    limit: int | None = None
    remove_bg: bool | None = None
    force: bool | None = False
    coloring: bool | None = False
    workflow: str | None = None
    # override การเจนรายครั้ง (ไม่แตะ config.yaml) — เว้น = ใช้ค่าใน config
    checkpoint: str | None = None
    width: int | None = None
    height: int | None = None
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    scheduler: str | None = None
    seed: int | None = None
    batch: int | None = None


class BundleReq(BaseModel):
    title: str | None = "My Collection"
    slugs: list[str] | None = None
    page_size: str | None = "A4"
    items: list[dict] | None = None
    page_numbers: bool | None = False
    cover: bool | None = True


class UploadReq(BaseModel):
    platform: str
    limit: int | None = None
    use_preview: bool | None = False
    validate_only: bool | None = False


class ConfigReq(BaseModel):
    updates: dict


class DeleteDesignReq(BaseModel):
    slug: str


class DeleteBundleReq(BaseModel):
    name: str


# ---------------- app ----------------
app = FastAPI(title="POD Studio")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/status")
def status():
    cfg = load_config()
    # ComfyUI ping
    comfy_ok = False
    try:
        import comfy_client
        c = cfg["comfyui"]
        comfy_ok = comfy_client.ComfyClient(
            host=c.get("host", "127.0.0.1"), port=c.get("port", 8188)
        ).ping()
    except Exception:
        comfy_ok = False
    # AI provider readiness (ตาม agents.provider)
    agents_cfg = cfg.get("agents", {})
    ai_ok = _provider_ready(agents_cfg)
    return {"comfyui": comfy_ok, "anthropic": ai_ok,
            "provider": (agents_cfg.get("provider") or "gemini")}


def _provider_ready(agents_cfg):
    from agents import base as abase
    provider = (agents_cfg.get("provider") or "gemini").lower()
    preset = abase.PROVIDERS.get(provider)
    if not preset:
        return False
    if provider == "ollama":
        try:
            import requests
            root = (agents_cfg.get("base_url") or preset["base_url"]).replace("/v1", "")
            return requests.get(root + "/api/tags", timeout=3).status_code == 200
        except Exception:
            return False
    return bool(abase._resolve_key(preset))


@app.post("/api/brainstorm")
def brainstorm(req: BrainstormReq):
    if not req.brief.strip():
        return JSONResponse({"error": "กรุณาใส่ไอเดีย/ธีม"}, status_code=400)
    cfg = load_config().get("agents", {})
    try:
        result = agent_team.run_team(
            brief=req.brief,
            count=req.count or cfg.get("default_count", 6),
            agents_cfg=cfg,
            product=req.product,
            options=req.options,
        )
        return result
    except AgentError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:  # pragma: no cover
        return JSONResponse({"error": f"เกิดข้อผิดพลาด: {e}"}, status_code=500)


@app.get("/api/prompts")
def get_prompts():
    return {"prompts": prompts_io.read_prompts()}


@app.post("/api/prompts")
def add_prompts(req: AddPromptsReq):
    added = prompts_io.append_prompts(req.rows)
    return {"added": added, "total": len(prompts_io.read_prompts())}


@app.post("/api/prompts/delete")
def delete_prompt(req: DeletePromptReq):
    return {"deleted": prompts_io.delete_prompt(req.title)}


@app.post("/api/generate")
def generate(req: GenerateReq):
    cmd = [sys.executable, os.path.join(SRC_DIR, "run_batch.py")]
    if req.limit:
        cmd += ["--limit", str(req.limit)]
    if req.force:
        cmd += ["--force"]
    if req.remove_bg is True:
        cmd += ["--remove-bg"]
    elif req.remove_bg is False:
        cmd += ["--keep-bg"]
    if req.coloring:
        cmd += ["--coloring"]
    if req.workflow:
        cmd += ["--workflow", req.workflow]
    # override การเจน (เฉพาะที่ส่งมา)
    for flag, val in {
        "--checkpoint": req.checkpoint, "--width": req.width, "--height": req.height,
        "--steps": req.steps, "--cfg": req.cfg, "--sampler": req.sampler,
        "--scheduler": req.scheduler, "--seed": req.seed, "--batch": req.batch,
    }.items():
        if val is not None and val != "":
            cmd += [flag, str(val)]
    return {"job_id": start_job(cmd)}


@app.post("/api/upload")
def upload(req: UploadReq):
    cmd = [sys.executable, os.path.join(SRC_DIR, "upload_runner.py"), "--platform", req.platform]
    if req.validate_only:
        cmd += ["--validate"]
    else:
        if req.limit:
            cmd += ["--limit", str(req.limit)]
        if req.use_preview:
            cmd += ["--use-preview"]
    return {"job_id": start_job(cmd)}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"error": "ไม่พบ job"}, status_code=404)
    return job


@app.post("/api/build-site")
def build_site_ep():
    try:
        return build_site.build()
    except Exception as e:  # pragma: no cover
        return JSONResponse({"error": f"สร้างเว็บร้านไม่สำเร็จ: {e}"}, status_code=500)


@app.post("/api/bundle")
def bundle(req: BundleReq):
    try:
        return bundle_pdf.build(
            slugs=req.slugs or None, title=req.title or "My Collection",
            page_size=req.page_size or "A4", items=req.items or None,
            page_numbers=bool(req.page_numbers), cover=req.cover is not False,
        )
    except Exception as e:
        return JSONResponse({"error": f"สร้าง PDF ไม่สำเร็จ: {e}"}, status_code=400)


@app.post("/api/bundle/upload")
async def bundle_upload(file: UploadFile):
    """อัปโหลดรูปเองเพื่อใส่ใน PDF — เก็บที่ output/bundle_assets/."""
    import re
    assets = os.path.join(OUTPUT_DIR, "bundle_assets")
    os.makedirs(assets, exist_ok=True)
    base = os.path.basename(file.filename or "image")
    base = re.sub(r"[^\w\-.]", "_", base) or "image"
    if not base.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        base += ".png"
    dest = os.path.join(assets, base)
    stem, ext = os.path.splitext(base)
    n = 1
    while os.path.exists(dest):  # กันชื่อชนกัน
        dest = os.path.join(assets, f"{stem}_{n}{ext}")
        n += 1
    with open(dest, "wb") as f:
        f.write(await file.read())
    rel = os.path.relpath(dest, PROJECT_ROOT).replace("\\", "/")
    return {"path": rel, "url": "/" + rel, "name": os.path.basename(dest)}


@app.get("/api/config")
def get_config():
    return config_io.read_config()


@app.post("/api/config")
def save_config(req: ConfigReq):
    try:
        result = config_io.update_config(req.updates or {})
        return {"ok": True, **result}
    except Exception as e:  # pragma: no cover
        return JSONResponse({"error": f"บันทึกไม่สำเร็จ: {e}"}, status_code=400)


@app.get("/api/comfy-meta")
def comfy_meta():
    """รายชื่อ checkpoint / sampler / scheduler จาก ComfyUI (ใช้ทำ dropdown)."""
    cfg = load_config()
    try:
        import comfy_client
        c = cfg["comfyui"]
        client = comfy_client.ComfyClient(
            host=c.get("host", "127.0.0.1"), port=c.get("port", 8188)
        )
        if not client.ping():
            return {"online": False, "checkpoints": [], "samplers": [], "schedulers": []}
        samplers, schedulers = client.list_samplers()

        def opts(node_class, field):
            try:
                info = client.object_info(node_class)
                return list(info[node_class]["input"]["required"][field][0])
            except Exception:
                return []

        return {
            "online": True,
            "checkpoints": client.list_checkpoints(),
            "samplers": samplers,
            "schedulers": schedulers,
            "unets": opts("UNETLoader", "unet_name"),
            "unets_gguf": opts("UnetLoaderGGUF", "unet_name"),
            "clips": opts("CLIPLoader", "clip_name"),
            "vaes": opts("VAELoader", "vae_name"),
        }
    except Exception:
        return {"online": False, "checkpoints": [], "samplers": [], "schedulers": [],
                "unets": [], "unets_gguf": [], "clips": [], "vaes": []}


@app.get("/api/workflows")
def list_workflows():
    """คลัง workflow ที่เลือกได้ (sdxl/flux2/...) + ตัวที่ใช้อยู่."""
    cfg = load_config()
    wfs = cfg.get("workflows", {}) or {}
    items = [{"name": k, "label": v.get("label", k), "negative": v.get("negative", True),
              "gguf": v.get("gguf", False)}
             for k, v in wfs.items()]
    return {"workflows": items, "active": cfg.get("generation", {}).get("workflow", "sdxl")}


@app.get("/api/catalog")
def catalog():
    import csv
    path = os.path.join(OUTPUT_DIR, "catalog.csv")
    if not os.path.exists(path):
        return {"items": []}
    items = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            preview = (r.get("preview_path") or r.get("image_path") or "").replace("\\", "/")
            full = (r.get("image_path") or "").replace("\\", "/")
            r["preview_url"] = "/" + preview if preview else ""
            r["image_url"] = "/" + full if full else r["preview_url"]
            items.append(r)
    items.reverse()  # ใหม่สุดก่อน
    return {"items": items}


@app.post("/api/catalog/delete")
def delete_design(req: DeleteDesignReq):
    try:
        return library.delete_design(req.slug)
    except Exception as e:
        return JSONResponse({"error": f"ลบไม่สำเร็จ: {e}"}, status_code=400)


@app.get("/api/bundles")
def bundles():
    return {"items": library.list_bundles()}


@app.post("/api/bundles/delete")
def delete_bundle(req: DeleteBundleReq):
    try:
        return library.delete_bundle(req.name)
    except Exception as e:
        return JSONResponse({"error": f"ลบไม่สำเร็จ: {e}"}, status_code=400)


# ---------------- ร้านค้า (admin) ----------------
class StoreProductReq(BaseModel):
    product: dict


class StoreDeleteReq(BaseModel):
    id: str


@app.get("/api/store/status")
def store_status():
    prods = store_products.load_products()
    return {
        "mode": store_payments.mode(),
        "products": len(prods),
        "active": sum(1 for p in prods if p.get("active")),
        "orders": len(store_orders.list_orders()),
        "paid": sum(1 for o in store_orders.list_orders() if o.get("status") == "paid"),
        "keys": {k: bool(v) for k, v in store_payments.get_keys().items()},
    }


@app.get("/api/store/products")
def store_products_list():
    return {"products": store_products.load_products()}


@app.post("/api/store/products")
def store_products_save(req: StoreProductReq):
    return store_products.upsert_product(req.product)


@app.post("/api/store/products/delete")
def store_products_delete(req: StoreDeleteReq):
    return {"deleted": store_products.delete_product(req.id)}


@app.get("/api/store/orders")
def store_orders_list():
    return {"items": store_orders.list_orders()}


@app.get("/api/store/products-tsv")
def store_products_tsv():
    """สร้าง TSV พร้อมวางลงชีต Products ของ Store.gs จากดีไซน์/PDF ที่มี.

    คอลัมน์: id, title, description, price, currency, image_url,
             drive_file_id(ว่าง), gumroad_url(ว่าง), active
    image_url = pages_base_url + previews/<slug>.jpg (ถ้าตั้ง) ไม่งั้น path สัมพัทธ์
    """
    from fastapi.responses import PlainTextResponse
    cfg = load_config()
    site = cfg.get("site", {})
    base = (site.get("pages_base_url") or "").rstrip("/")
    price = site.get("price", 290)
    currency = (site.get("currency", "thb")).lower()
    header = ["id", "title", "description", "price", "currency",
              "image_url", "drive_file_id", "gumroad_url", "active"]
    rows = [header]

    def img_url(slug):
        rel = f"previews/{slug}.jpg"
        return f"{base}/{rel}" if base else rel

    # ดีไซน์จาก catalog (ไม่ซ้ำ slug)
    import csv as _csv
    cat_path = os.path.join(OUTPUT_DIR, "catalog.csv")
    if os.path.exists(cat_path):
        seen = set()
        with open(cat_path, "r", encoding="utf-8-sig", newline="") as f:
            for r in _csv.DictReader(f):
                slug = (r.get("slug") or "").strip()
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                rows.append([slug, r.get("title") or slug, "", price, currency,
                             img_url(slug), "", "", "true"])
    # E-book PDF
    for b in library.list_bundles():
        name = b["name"].rsplit(".", 1)[0]
        rows.append([name, b["name"], f"{b.get('pages','')} หน้า PDF", price, currency,
                     "", "", "", "true"])

    tsv = "\n".join("\t".join(str(c) for c in row) for row in rows)
    return PlainTextResponse(tsv, media_type="text/tab-separated-values")


@app.get("/api/store/sources")
def store_sources():
    """แหล่งไฟล์ที่เอามาทำสินค้าได้: PDF (E-book) + ดีไซน์ใน catalog."""
    src = []
    for b in library.list_bundles():
        rel = "output/bundles/" + b["name"]
        src.append({"kind": "pdf", "title": b["name"], "file": rel,
                    "preview": "", "pages": b.get("pages")})
    import csv as _csv
    cat_path = os.path.join(OUTPUT_DIR, "catalog.csv")
    if os.path.exists(cat_path):
        seen = set()
        with open(cat_path, "r", encoding="utf-8-sig", newline="") as f:
            for r in _csv.DictReader(f):
                slug = (r.get("slug") or "").strip()
                if not slug or slug in seen:
                    continue
                seen.add(slug)
                img = (r.get("image_path") or "").replace("\\", "/")
                prev = (r.get("preview_path") or r.get("image_path") or "").replace("\\", "/")
                src.append({"kind": "design", "title": r.get("title") or slug,
                            "file": img, "preview": ("/" + prev) if prev else ""})
    return {"sources": src}


# รวมเส้นทางฝั่งลูกค้า /store/* + เสิร์ฟไฟล์ storefront
app.include_router(store_web.router)
app.mount("/store/static", StaticFiles(directory=store_web.STOREFRONT_DIR), name="storefront")

# เสิร์ฟไฟล์ภาพที่สร้าง + static ของหน้าเว็บ + พรีวิวหน้าร้าน
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")
app.mount("/shop", StaticFiles(directory=DOCS_DIR, html=True), name="shop")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    import sys

    port = 8500
    if len(sys.argv) > 2 and sys.argv[1] == "--port":
        try:
            port = int(sys.argv[2])
        except ValueError:
            pass

    print(f"POD Studio running at:  http://127.0.0.1:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
