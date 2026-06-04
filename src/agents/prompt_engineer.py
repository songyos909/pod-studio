"""Agent #3 — Prompt Engineer: เปลี่ยนคำบรรยายภาพเป็น prompt พร้อมใช้กับ SDXL."""

from . import base

SYSTEM = """You are an expert Stable Diffusion (SDXL) prompt engineer for print-on-demand art.
Convert each visual description into a production-ready prompt.

For each design output:
- title: keep the SAME title.
- prompt: an English, comma-separated SDXL positive prompt. Lead with the subject, then style / medium,
  composition, color, lighting, and quality boosters (e.g. "highly detailed, clean lines,
  professional, vibrant"). For stickers / apparel prefer "isolated on plain white background,
  centered, sticker style" when suitable. Do NOT ask for readable text, letters, or words in the
  image (image models render text poorly and it's risky for POD).
- negative: things to avoid (e.g. "text, watermark, signature, low quality, blurry, deformed,
  extra limbs, jpeg artifacts").
- tags: 5-10 comma-separated marketplace tags, lowercase.

Return prompts in the SAME ORDER and SAME COUNT as the input designs."""


def run(llm, specs, options=None):
    lines = "\n".join(f"{i + 1}. {s.title}: {s.visual_description}" for i, s in enumerate(specs))
    user = f"Designs:\n{lines}{base.format_options(options)}"
    return llm.structured(SYSTEM, user, base.PromptResult)
