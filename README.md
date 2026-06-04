# ระบบ Automate สร้างดีไซน์ Print-on-Demand ด้วย ComfyUI

สร้างรูปภาพดีไซน์เป็น batch อัตโนมัติด้วย ComfyUI (Stable Diffusion) บนเครื่องตัวเอง
แล้วเตรียมไฟล์ความละเอียดสูงพร้อมขาย + เก็บ metadata เป็นระบบ
เพื่อนำไปขายออนไลน์ (Print-on-Demand / Etsy / Shopify)

## สิ่งที่ต้องมีก่อน
- ติดตั้ง **ComfyUI** และเปิดให้รันอยู่ (ค่าเริ่มต้น `http://127.0.0.1:8188`)
- การ์ดจอ NVIDIA (มีอยู่แล้ว)
- Python 3.10+ บน Windows

## ติดตั้ง
```powershell
cd D:\automate_video
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## วิธีที่ง่ายที่สุด: เปิดหน้าเว็บ UI 🌐
ควบคุมทุกอย่างผ่านหน้าเว็บ (ให้ AI ช่วยคิด → จัดการ prompt → สร้างภาพ → ดูแกลเลอรี → อัปโหลด)
```powershell
python src/webapp/server.py
```
แล้วเปิดเบราว์เซอร์ที่ **http://127.0.0.1:8500**

แท็บในหน้าเว็บ:
- **🧠 AI Studio** — พิมพ์ไอเดีย/ธีม แล้วทีม AI (Art Director → Designer → Prompt Engineer) ช่วยคิด prompt ให้ เลือกที่ชอบกดเพิ่มเข้า `prompts.csv`
- **📝 Prompts** — ดู/เพิ่ม/ลบรายการดีไซน์
- **⚙️ สร้างภาพ** — สั่ง generate (มี log สด) ผ่าน ComfyUI
- **🖼️ แกลเลอรี** — ดูดีไซน์ที่สร้างแล้ว
- **🚀 อัปโหลดขาย** — ทดสอบเชื่อมต่อ + อัปขึ้น Etsy/Shopify

### ทีม AI agents (ต้องมี Claude API key)
ทีม AI เลือก provider ได้ที่ `config.yaml → agents.provider` — **มีตัวฟรีให้เลือก**:

| provider | ฟรี? | ตั้งคีย์ยังไง |
|---|---|---|
| `gemini` (ดีฟอลต์) | ✅ free tier | คีย์ฟรี https://aistudio.google.com/apikey → `$env:GEMINI_API_KEY="..."` หรือ `gemini.api_key` ใน credentials.yaml |
| `ollama` | ✅ ฟรี 100% | ไม่ต้องมีคีย์ — ลง [Ollama](https://ollama.com) → `ollama pull llama3.1` → ตั้ง `provider: ollama` |
| `groq` | ✅ free tier | คีย์ฟรี https://console.groq.com/keys → `$env:GROQ_API_KEY="..."` |
| `anthropic` | 💵 เสียเงิน | `$env:ANTHROPIC_API_KEY="sk-ant-..."` (คุณภาพสูงสุด) |
| `openai` | 💵 เสียเงิน | `$env:OPENAI_API_KEY="sk-..."` |

ไฟสถานะ "AI Team" บนหัวเว็บจะเป็นสีเขียวเมื่อ provider ที่เลือกพร้อมใช้ (มีคีย์ / Ollama รันอยู่)

## ตั้งค่าก่อนใช้งานครั้งแรก
แก้ไฟล์ `config.yaml`:

1. **`generation.checkpoint`** — ชื่อไฟล์โมเดลในโฟลเดอร์ `ComfyUI\models\checkpoints`
   (ตั้งไว้แล้วเป็น `sd_xl_base_1.0.safetensors` — เปลี่ยนเป็นโมเดลอื่นได้)
2. **`generation.width/height`** — SD1.5 ใช้ 512–768, SDXL ใช้ 1024
3. **`upscale`** — อัปสเกลด้วย NVIDIA RTX ในตัว ComfyUI (`method: rtx`, `scale: 4.0`,
   `quality: ULTRA`) คมกว่า Pillow มาก / ตั้ง `method: none` เพื่อปิด
4. **`postprocess.target_width/height/dpi`** — ขนาดไฟล์พร้อมขาย
   (ค่าเริ่มต้น 4500×5400 @ 300dpi ≈ 15×18 นิ้ว เหมาะกับสกรีนเสื้อ)
5. **`postprocess.background`** — `transparent` (พื้นโปร่ง) หรือ `white`
6. **`postprocess.remove_background`** — `true` เพื่อตัดพื้นหลังจริงด้วย rembg

### ใช้ workflow ของตัวเอง (แนะนำ)
ไฟล์ `workflows/pod_base.json` เป็น workflow มาตรฐาน (Checkpoint → KSampler → SaveImage)
ถ้าอยากใช้ workflow ที่คุณตั้งเองใน ComfyUI:
1. ใน ComfyUI กดเมนู → **Save (API Format)**
2. เซฟทับไฟล์ `workflows/pod_base.json`
3. เปิดดูเลข node id แล้วแก้ `workflow.nodes` ใน `config.yaml` ให้ตรง
   (ชี้ไปที่ node prompt บวก/ลบ, EmptyLatentImage, KSampler, CheckpointLoader, SaveImage)

## ใส่ไอเดียดีไซน์
แก้ไฟล์ `prompts.csv` (เปิดด้วย Excel หรือ text editor ก็ได้) — 1 แถว = 1 ดีไซน์:

| คอลัมน์ | ความหมาย |
|---|---|
| `title` | ชื่อดีไซน์ (ใช้ตั้งชื่อโฟลเดอร์/ไฟล์) |
| `prompt` | คำสั่งสร้างภาพ (บังคับ) |
| `negative` | สิ่งที่ไม่อยากได้ (เว้นว่าง = ใช้ค่า default ใน config) |
| `seed` | เลข seed (เว้นว่าง = สุ่ม) |
| `tags` | แท็ก คั่นด้วยจุลภาค (เก็บไว้ใช้ตอนลงขาย) |

## รัน
```powershell
python src/run_batch.py --limit 1     # ทดสอบ 1 ภาพก่อน
python src/run_batch.py               # ทำทุกแถวใน prompts.csv
python src/run_batch.py --force       # สร้างใหม่แม้เคยทำแล้ว
python src/run_batch.py --remove-bg   # บังคับลบพื้นหลังรอบนี้ (override config)
python src/run_batch.py --keep-bg     # บังคับไม่ลบพื้นหลังรอบนี้
python src/run_batch.py --workflow flux2   # ใช้ Flux.2 dev แทน SDXL
```
**เลือก workflow ได้:** ตั้ง `generation.workflow` ใน config (`sdxl` | `flux2`) หรือเลือกในแท็บ "สร้างภาพ" → กล่อง "ตัวเลือกการเจน"
- `sdxl` — เร็ว มี negative prompt (ดีฟอลต์)
- `flux2` — Flux.2 dev คุณภาพสูง ไม่มี negative (ใช้ค่า guidance = CFG ~4) ต้องมีโมเดล `flux2_dev_fp8mixed` + `mistral_3_small_flux2_bf16` + vae `full_encoder_small_decoder` ใน ComfyUI
- `flux2-turbo` — **เร็วกว่า ~2.5 เท่า** (8 steps ด้วย Turbo LoRA) ใช้โมเดลชุดเดียวกับ flux2 — ใช้ได้ทันทีถ้ามี `Flux_2-Turbo-LoRA_comfyui.safetensors` ใน `models/loras`
- `flux2-gguf` — **โมเดลเล็ก/เร็ว สำหรับการ์ดจอ VRAM น้อย** ใช้ผ่าน ComfyUI-GGUF
  - ต้องโหลดไฟล์ `.gguf` ของ Flux.2 (เช่น `flux2-dev-Q4_K_M.gguf` ~7GB เล็กกว่า fp8 มาก) วางใน `ComfyUI/models/unet/`
  - แหล่งโหลด: ค้น "FLUX.2 dev GGUF" บน Hugging Face (เช่นของ city96/QuantStack) เลือก Q4_K_M (สมดุล) หรือ Q3 (เล็กสุด)
  - ใช้ text encoder (`mistral_3_small_flux2_bf16`) + vae เดิมได้เลย ไม่ต้องโหลดเพิ่ม
  - แล้วเลือกชื่อไฟล์ใน Settings หรือแก้ `config.yaml → workflows.flux2-gguf.models.checkpoint`
- เพิ่ม workflow เองได้ใน `config.yaml → workflows:` (ระบุ path + map ว่าพารามิเตอร์ไปลง node ไหน)
ขั้นตอนต่อภาพ: ComfyUI generate → **RTX upscale** → (ถ้าเปิด) **ลบพื้นหลัง** →
จัดขนาด+ฝัง DPI ด้วย Pillow → เก็บไฟล์

## ผลลัพธ์
```
output/
├── catalog.csv                         # รวมทุกดีไซน์ (ไว้ใช้กรอกตอนลงขาย)
└── 2026-06-04/
    └── galaxy-cat-sticker/
        ├── galaxy-cat-sticker.png      # ไฟล์ความละเอียดสูงพร้อมขาย
        ├── galaxy-cat-sticker_preview.jpg
        └── metadata.json               # prompt, seed, ขนาด, ฯลฯ
```
> ระบบจะ **ข้าม** ดีไซน์ที่มี `title`/slug ซ้ำกับที่เคยสร้างไว้ (กันทำซ้ำ) — ใช้ `--force` เพื่อสร้างใหม่

## เครื่องมือลบพื้นหลัง (ใช้เดี่ยว ๆ ได้)
นอกจากเปิดในขั้น batch แล้ว ยังเรียกตรง ๆ กับไฟล์ที่มีอยู่ได้:
```powershell
python src/remove_bg.py รูป.png                 # -> รูป_nobg.png
python src/remove_bg.py รูป.png ออก.png
python src/remove_bg.py --dir โฟลเดอร์           # ทำทั้งโฟลเดอร์
python src/remove_bg.py รูป.png --model isnet-general-use
```
> ครั้งแรกจะดาวน์โหลดโมเดล (~170MB) เก็บที่ `~/.u2net` หลังจากนั้นทำงาน offline ได้

## อัปโหลดขึ้น Etsy / Shopify
อ่านรายการจาก `output/catalog.csv` แล้วสร้าง listing ให้อัตโนมัติ
```powershell
# 1) เตรียมคีย์: ก๊อป credentials.example.yaml -> credentials.yaml แล้วกรอกค่า
# 2) (Etsy) ยืนยันสิทธิ์ครั้งแรก
python src/upload_runner.py --platform etsy --auth
# 3) เช็กการเชื่อมต่อก่อนอัปจริง
python src/upload_runner.py --platform shopify --validate
# 4) อัปโหลด (เริ่มเป็น draft ก่อน ปลอดภัยกว่า)
python src/upload_runner.py --platform shopify --limit 1
python src/upload_runner.py --platform etsy --limit 1 --use-preview
```
- ตั้งราคา/คำอธิบาย/หมวดหมู่ได้ที่ `config.yaml` ส่วน `listing:`
- กันอัปซ้ำด้วย `output/upload_state.json` (ใช้ `--force` เพื่ออัปซ้ำ)
- **ต้องใช้ API key ของคุณเอง** — โค้ดพร้อมแล้วแต่ผมทดสอบ live ให้ไม่ได้เพราะไม่มีคีย์/ร้านจริง
  ใช้ `--validate` ตรวจว่าเชื่อมต่อผ่านก่อนเสมอ
- Etsy ต้องตั้ง `listing.etsy.taxonomy_id` และ `shipping_profile_id` ให้ตรงสินค้าจริง

## หนังสือระบายสี + รวมเป็น PDF ขาย 📕
**โหมดระบายสี (lineart)** — สร้างภาพลายเส้นขาว-ดำจาก prompt เดิม (เก็บแยก slug ลงท้าย `-coloring`):
```powershell
python src/run_batch.py --coloring --limit 5     # หรือเช็กบ็อกซ์ "โหมดหนังสือระบายสี" ในแท็บสร้างภาพ
```
> ได้ผลดีกับ subject ที่พื้นหลังโล่ง (เช่น ดอกไม้/มังกร/มันดาลา) — เลี่ยง prompt ที่มีฉากมืดเต็มภาพ

**รวมเป็น PDF พร้อมขาย** — เลือกดีไซน์ → ไฟล์ PDF มีหน้าปก (A4/Letter @300dpi):
```powershell
python src/bundle_pdf.py --title "Wildflower Coloring Book"   # หรือใช้แท็บ "PDF/หนังสือ" ในหน้าเว็บ
```
ไฟล์ออกที่ `output/bundles/*.pdf` → เอาขึ้น **Gumroad/Etsy/Amazon KDP** ขายเป็นดาวน์โหลดได้เลย

## เว็บร้านขายเอง (สร้างไว้บนเครื่องแล้ว → ขึ้น GitHub Pages ภายหลัง)
หน้าร้าน static อยู่ในโฟลเดอร์ `docs/` — สร้าง/อัปเดตข้อมูลร้านจาก catalog ด้วย:
```powershell
python src/build_site.py          # หรือกดปุ่มในแท็บ "เว็บร้าน" บนหน้าเว็บ UI
```
- พรีวิวในเครื่อง: เปิด UI แล้วกด "เปิดหน้าร้าน" (http://127.0.0.1:8500/shop/)
- ตั้งชื่อร้าน/ราคา/ช่องทางติดต่อได้ที่ `config.yaml` ส่วน `site:`

### รับออเดอร์อัตโนมัติ (Google Apps Script) — ทำทีหลังได้
ดู [gas/README.md](gas/README.md): สร้าง Google Sheet → วางโค้ด `gas/Code.gs` → Deploy เป็น Web app →
เอาลิงก์ `/exec` ใส่ `config.yaml → site.gas_url` แล้ว build ใหม่
(ยังไม่ตั้ง ฟอร์มสั่งซื้อจะเปิดอีเมลให้ลูกค้าส่งหาแทนไปก่อน)

### เอาขึ้น GitHub Pages (ภายหลัง)
1. `git init` + push โปรเจกต์ขึ้น GitHub
2. Settings → Pages → Source: **Deploy from a branch**, โฟลเดอร์ **/docs**
3. (ถ้ามีโดเมนเอง) ใส่ไฟล์ `CNAME` ในโฟลเดอร์ docs/ + ตั้ง DNS
> สถาปัตยกรรม + เฟสถัดไป (ระบบจ่ายเงิน/โดเมน) อยู่ใน [docs/website_plan.md](docs/website_plan.md)

## 🛒 ร้านขายไฟล์ดิจิทัลบน PC (Stripe Checkout) — ขายได้จริง
ระบบขายครบวงจรที่รันในเครื่อง: ลูกค้าจ่ายผ่าน Stripe → ได้ลิงก์ดาวน์โหลดอัตโนมัติ (ลิงก์หมดอายุ + จำกัดจำนวนครั้ง)

**เปิดใช้:**
- หน้าจัดการ (คุณ): เปิด UI → แท็บ **"ร้านขาย"** → เลือกไฟล์ (E-book/ดีไซน์) ตั้งราคา → บันทึกสินค้า
- หน้าร้าน (ลูกค้า): `http://127.0.0.1:8500/store`

**โหมดทดสอบ (ค่าเริ่มต้น — ไม่ต้องตั้งอะไร):** ยังไม่ใส่คีย์ Stripe = จำลองการจ่าย ลองระบบส่งไฟล์ได้เลย

**เปิดรับเงินจริง (3 ขั้น):**
```powershell
# 1) ขอคีย์ที่ https://dashboard.stripe.com/apikeys (เริ่มที่ Test mode)
#    ใส่ใน credentials.yaml -> stripe.secret_key / publishable_key
# 2) ทดสอบ webhook + ส่งไฟล์อัตโนมัติบนเครื่อง (ติดตั้ง Stripe CLI ก่อน)
stripe listen --forward-to localhost:8500/store/webhook
#    เอา whsec_... ที่ได้ ใส่ credentials.yaml -> stripe.webhook_secret
# 3) จ่ายทดสอบด้วยบัตร 4242 4242 4242 4242 (วันหมดอายุอนาคต, CVC อะไรก็ได้)
```
- พร้อมขายจริง: สลับเป็นคีย์ `sk_live_...` / `pk_live_...` ใน Stripe Dashboard (THB รองรับบัตร + **PromptPay**)
- ให้ลูกค้านอกบ้านเข้าถึง PC: ใช้ tunnel เช่น `cloudflared tunnel --url http://localhost:8500` (PC ต้องเปิดเครื่องไว้) หรือย้ายไปโฮสต์จริงภายหลัง
- ตั้งชื่อร้าน/สกุลเงิน/วันหมดอายุลิงก์ได้ที่ `config.yaml → store:`

> ความปลอดภัย: เงินเข้าบัญชี Stripe ของคุณโดยตรง โปรเจกต์ไม่เก็บเลขบัตร (Stripe จัดการหน้าจ่ายเอง) — คีย์อยู่ใน `credentials.yaml` ซึ่งถูก gitignore ไม่ขึ้น git

## หมายเหตุ
- ก่อนลงขายจริง ตรวจสอบนโยบาย/ลิขสิทธิ์ของแต่ละแพลตฟอร์มเรื่องภาพที่สร้างด้วย AI ด้วย
