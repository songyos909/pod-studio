"""ตัวประสานงานทีม: Art Director -> Designer -> Prompt Engineer (อย่างละ 1 ครั้งแบบ batch).

รองรับหลาย provider ผ่าน config["agents"] (anthropic/gemini/groq/ollama/openai).
คืนรายการดีไซน์พร้อม prompt ที่เอาไปใส่ prompts.csv ได้เลย.
"""

from . import art_director, base, designer, prompt_engineer


def run_team(brief, count=6, agents_cfg=None, product=None, on_progress=None, options=None):
    agents_cfg = agents_cfg or {}
    count = count or agents_cfg.get("default_count", 6)
    product = product or agents_cfg.get("product", "print-on-demand designs")
    llm = base.make_llm(agents_cfg)

    def progress(stage, msg):
        if on_progress:
            on_progress(stage, msg)

    progress("art_director", "Art Director กำลังคิดทิศทางและคอนเซปต์...")
    ad = art_director.run(llm, brief, count, product, options)

    progress("designer", "Designer กำลังออกแบบรายละเอียดภาพ...")
    design = designer.run(llm, brief, ad.art_direction, ad.concepts, product, options)

    progress("prompt_engineer", "Prompt Engineer กำลังเขียน prompt สำหรับ SDXL...")
    pe = prompt_engineer.run(llm, design.specs, options)

    n = min(len(ad.concepts), len(design.specs), len(pe.prompts))
    designs = []
    for i in range(n):
        p = pe.prompts[i]
        designs.append({
            "title": (p.title or ad.concepts[i].title).strip(),
            "prompt": p.prompt.strip(),
            "negative": p.negative.strip(),
            "tags": p.tags.strip(),
            "idea": ad.concepts[i].idea.strip(),
            "rationale": ad.concepts[i].rationale.strip(),
            "visual_description": design.specs[i].visual_description.strip(),
        })

    progress("done", f"เสร็จแล้ว {len(designs)} ดีไซน์")
    return {"provider": llm.provider, "model": llm.model,
            "art_direction": ad.art_direction.strip(), "designs": designs}
