"""พื้นฐานของทีม agents: รองรับหลาย provider (เลือกใน config.yaml > agents.provider).

- anthropic : Claude (เสียเงิน) — structured output ด้วย messages.parse
- gemini    : Google Gemini (มี free tier) — ผ่าน OpenAI-compatible endpoint
- groq      : Groq (มี free tier) — OpenAI-compatible
- ollama    : รันในเครื่อง ฟรี 100% ไม่ต้องมีคีย์ — OpenAI-compatible
- openai    : OpenAI ทั่วไป
ตัวที่ไม่ใช่ anthropic ใช้ JSON mode + parse ด้วย Pydantic (รองรับได้ทุกเจ้า)
"""

import json
import os

from pydantic import BaseModel

# ---------- preset ของแต่ละ provider ----------
PROVIDERS = {
    "anthropic": {"default_model": "claude-opus-4-8", "key_env": "ANTHROPIC_API_KEY", "cred": "anthropic"},
    "gemini": {
        "default_model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY", "cred": "gemini",
    },
    "groq": {
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY", "cred": "groq",
    },
    "ollama": {
        "default_model": "llama3.1",
        "base_url": "http://127.0.0.1:11434/v1",
        "key_env": "OLLAMA_API_KEY", "cred": "ollama", "no_key": True,
    },
    "openai": {"default_model": "gpt-4o-mini", "key_env": "OPENAI_API_KEY", "cred": "openai"},
}


class AgentError(Exception):
    pass


# ---------- โมเดลข้อมูล (structured outputs) ----------
class Concept(BaseModel):
    title: str
    idea: str
    rationale: str


class ArtDirectionResult(BaseModel):
    art_direction: str
    concepts: list[Concept]


class DesignSpec(BaseModel):
    title: str
    visual_description: str


class DesignResult(BaseModel):
    specs: list[DesignSpec]


class PodPrompt(BaseModel):
    title: str
    prompt: str
    negative: str
    tags: str


class PromptResult(BaseModel):
    prompts: list[PodPrompt]


# ---------- หา API key ----------
def _resolve_key(preset):
    key = os.environ.get(preset["key_env"])
    if not key:
        try:
            import sys
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from upload import common
            creds = common.load_credentials()
            key = (creds.get(preset["cred"]) or {}).get("api_key")
        except Exception:
            key = None
    return key


def _ollama_models(base_url):
    """รายชื่อโมเดลที่ติดตั้งใน Ollama (เช่น ['llama3.1:8b', 'gemma4:latest'])."""
    import requests
    root = (base_url or "http://127.0.0.1:11434/v1").replace("/v1", "")
    try:
        data = requests.get(root + "/api/tags", timeout=5).json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _resolve_ollama_model(base_url, requested):
    """จับคู่ชื่อโมเดลที่ขอกับที่ติดตั้งจริง (เติม tag ให้/เลือกตัวที่มี).

    - ตรงเป๊ะ -> ใช้เลย
    - ขอแบบไม่มี tag (llama3.1) แต่มี llama3.1:8b -> ใช้ตัวที่มี tag
    - หาไม่เจอ -> เลือกตัวทั่วไปที่ไม่ใช่โมเดลโค้ด หรือ raise พร้อมรายชื่อ
    """
    installed = _ollama_models(base_url)
    if not installed:
        # ดึงรายชื่อไม่ได้ (Ollama อาจปิด) — ปล่อยให้ใช้ชื่อที่ขอไปก่อน
        return requested
    if requested in installed:
        return requested
    # เติม tag: llama3.1 -> llama3.1:8b
    prefix = requested.split(":")[0]
    for name in installed:
        if name.split(":")[0] == prefix:
            return name
    # เลือกตัวทั่วไป (เลี่ยงโมเดลเฉพาะทางอย่าง coder/embed)
    general = [n for n in installed if not any(k in n.lower() for k in ("coder", "embed", "code"))]
    pick = (general or installed)[0]
    return pick


def format_options(options):
    """แปลง dict ตัวเลือกครีเอทีฟเป็นบล็อก constraints ต่อท้าย user prompt.

    คีย์ที่รองรับ: style, camera, palette, mood, audience, extra
    คืน "" ถ้าไม่มีอะไรเลย (ทีมจะทำงานแบบอิสระเหมือนเดิม).
    """
    if not options:
        return ""
    labels = {
        "style": "Art style",
        "camera": "Camera angle / composition",
        "palette": "Color palette",
        "mood": "Mood",
        "audience": "Target audience / occasion",
    }
    lines = []
    for key, label in labels.items():
        val = (options.get(key) or "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    extra = (options.get("extra") or "").strip()
    if extra:
        lines.append(f"- Additional instructions: {extra}")
    if not lines:
        return ""
    return (
        "\n\nApply these creative constraints to EVERY concept/design "
        "(keep them consistent across the whole set):\n" + "\n".join(lines)
    )


def _strip_fences(text):
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


# ---------- LLM wrapper ----------
class AgentLLM:
    def __init__(self, provider, client, model):
        self.provider = provider
        self.client = client
        self.model = model

    def structured(self, system, user, output_format, max_tokens=8000):
        if self.provider == "anthropic":
            return self._anthropic(system, user, output_format, max_tokens)
        return self._openai_compat(system, user, output_format, max_tokens)

    def _anthropic(self, system, user, output_format, max_tokens):
        kwargs = dict(
            model=self.model, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_format=output_format,
        )
        try:
            resp = self.client.messages.parse(thinking={"type": "adaptive"}, **kwargs)
        except Exception as e:
            try:
                resp = self.client.messages.parse(**kwargs)
            except Exception:
                raise AgentError(f"เรียก Claude ไม่สำเร็จ: {e}") from e
        if resp.parsed_output is None:
            raise AgentError("Claude ไม่คืนผลลัพธ์ตาม schema")
        return resp.parsed_output

    def _openai_compat(self, system, user, output_format, max_tokens):
        schema = json.dumps(output_format.model_json_schema(), ensure_ascii=False)
        sys_full = (
            f"{system}\n\nReturn ONLY one JSON object that matches this JSON Schema. "
            f"No markdown, no code fences, no commentary.\nJSON Schema:\n{schema}"
        )
        messages = [{"role": "system", "content": sys_full}, {"role": "user", "content": user}]
        kwargs = dict(model=self.model, messages=messages, max_tokens=max_tokens, temperature=0.7)
        try:
            resp = self.client.chat.completions.create(
                response_format={"type": "json_object"}, **kwargs)
        except Exception:
            # บาง provider ไม่รองรับ response_format -> ลองใหม่แบบไม่มี
            try:
                resp = self.client.chat.completions.create(**kwargs)
            except Exception as e:
                raise AgentError(f"เรียก {self.provider} ไม่สำเร็จ: {e}") from e
        text = _strip_fences(resp.choices[0].message.content)
        try:
            return output_format.model_validate_json(text)
        except Exception as e:
            raise AgentError(f"{self.provider} คืน JSON ไม่ตรง schema: {e}") from e


def make_llm(agents_cfg):
    """สร้าง AgentLLM ตาม config (agents.provider/model/base_url)."""
    agents_cfg = agents_cfg or {}
    provider = (agents_cfg.get("provider") or "gemini").lower()
    if provider not in PROVIDERS:
        raise AgentError(f"provider ไม่รู้จัก: {provider} (เลือก {list(PROVIDERS)})")
    preset = PROVIDERS[provider]
    model = agents_cfg.get("model") or preset["default_model"]
    base_url = agents_cfg.get("base_url") or preset.get("base_url")
    key = _resolve_key(preset)

    if provider == "anthropic":
        try:
            import anthropic
        except ImportError as e:
            raise AgentError("ต้องติดตั้ง anthropic: pip install anthropic") from e
        if not key:
            raise AgentError("ไม่พบ ANTHROPIC_API_KEY (env หรือ credentials.yaml)")
        return AgentLLM(provider, anthropic.Anthropic(api_key=key), model)

    # OpenAI-compatible (gemini/groq/ollama/openai)
    try:
        import openai
    except ImportError as e:
        raise AgentError("ต้องติดตั้ง openai: pip install openai") from e
    if not key and not preset.get("no_key"):
        raise AgentError(
            f"ไม่พบคีย์สำหรับ {provider} — ตั้ง env {preset['key_env']} "
            f"หรือใส่ {preset['cred']}.api_key ใน credentials.yaml"
        )
    if provider == "ollama":
        # จับคู่ชื่อโมเดลกับที่ติดตั้งจริง (เฉพาะตอนผู้ใช้ไม่ได้ระบุ tag เป๊ะ)
        installed = _ollama_models(base_url)
        if installed and model not in installed:
            resolved = _resolve_ollama_model(base_url, model)
            if resolved not in installed:
                raise AgentError(
                    f"ไม่พบโมเดล '{model}' ใน Ollama — ที่ติดตั้งอยู่: {', '.join(installed)}. "
                    f"โหลดเพิ่มด้วย `ollama pull {model}` หรือแก้ agents.model ใน config.yaml"
                )
            model = resolved

    client = openai.OpenAI(api_key=key or "ollama", base_url=base_url)
    return AgentLLM(provider, client, model)
