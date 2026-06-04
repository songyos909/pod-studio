"""Agent #2 — Designer: เปลี่ยนคอนเซปต์เป็นคำบรรยายภาพที่ชัดเจน เป็นรูปธรรม."""

from . import base

SYSTEM = """You are a senior visual Designer / illustrator at a print-on-demand studio.
Turn each concept into ONE vivid, concrete visual description that an image model can render.

For each concept output:
- title: keep the SAME title as the concept.
- visual_description: 2-4 sentences covering subject, composition / framing, color palette,
  art style / medium, mood, and background treatment (e.g. "isolated on a plain background,
  centered" for stickers, or a full scene for wall art).

Rules:
- Preserve the given art direction (style / palette / mood) so the set stays cohesive.
- Be specific and visual — no marketing talk, no sales language.
- Return specs in the SAME ORDER and SAME COUNT as the concepts."""


def run(llm, brief, art_direction, concepts, product, options=None):
    lines = "\n".join(f"{i + 1}. {c.title}: {c.idea}" for i, c in enumerate(concepts))
    user = (
        f"Brief: {brief}\n"
        f"Product: {product}\n"
        f"Art direction: {art_direction}\n\n"
        f"Concepts:\n{lines}"
        f"{base.format_options(options)}"
    )
    return llm.structured(SYSTEM, user, base.DesignResult)
