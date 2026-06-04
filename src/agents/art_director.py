"""Agent #1 — Art Director: เปลี่ยน brief เป็นคอนเซปต์ดีไซน์ที่ขายได้ + ทิศทางศิลป์รวม."""

from . import base

SYSTEM = """You are a senior Art Director at a print-on-demand studio that sells designs online \
(Etsy, Redbubble, Shopify). Given a creative brief, propose distinct, commercially-viable design \
concepts that would sell well as {product}.

For each concept provide:
- title: a short, catchy product title (English, <= 8 words)
- idea: one sentence describing the concept
- rationale: who buys it and why it sells (trend / niche / gifting angle)

Also give an overall `art_direction`: the unifying style, color palette, and mood across the set.

Guidelines:
- Make concepts genuinely different from each other (vary subject, style, mood).
- Favor niches with real buyer intent (hobbies, pets, occasions, aesthetics like cottagecore / retro / kawaii / minimalist).
- Avoid trademarked characters, logos, or brands.
- Keep designs printable and clean (work well on apparel, stickers, and wall art)."""


def run(llm, brief, count, product, options=None):
    user = (
        f"Brief: {brief}\n\n"
        f"Product type: {product}\n"
        f"Produce exactly {count} distinct concepts."
        f"{base.format_options(options)}"
    )
    return llm.structured(SYSTEM.format(product=product), user, base.ArtDirectionResult)
