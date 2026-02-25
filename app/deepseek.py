# app/deepseek.py
import base64
import os
import aiohttp

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_TEXT_MODEL = os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-chat")
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY is not set")


def _endpoint() -> str:
    # DeepSeek обычно совместим с OpenAI-style: /v1/chat/completions
    return f"{DEEPSEEK_BASE_URL}/v1/chat/completions"


def _clean_output(s: str) -> str:
    # Убираем частые "кривые" обвязки, чтобы не было \\( \\) и \\[ \\]
    s = s.replace("\\(", "").replace("\\)", "")
    s = s.replace("\\[", "").replace("\\]", "")
    s = s.replace("```", "")
    return s.strip()


async def ask_deepseek_text(prompt: str) -> str:
    url = _endpoint()
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    system = (
        "Ты помощник по учебе. "
        "Отвечай обычным текстом без LaTeX-обёрток вида \\( \\), \\[ \\]. "
        "Если нужны формулы — пиши их простым текстом (например: x^2 - 2x + 1). "
        "Не используй тройные кавычки/кодовые блоки."
    )

    payload = {
        "model": DEEPSEEK_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=120) as r:
            txt = await r.text()
            if r.status != 200:
                raise RuntimeError(f"DeepSeek error {r.status}: {txt}")
            data = await r.json()

    content = data["choices"][0]["message"]["content"]
    return _clean_output(content)


async def ask_deepseek_vision(prompt: str, image_bytes: bytes, mime: str = "image/jpeg") -> str:
    url = _endpoint()
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    system = (
        "Ты помощник по учебе. "
        "Сначала аккуратно распознай текст задания с изображения, затем реши. "
        "Отвечай обычным текстом без LaTeX-обёрток вида \\( \\), \\[ \\]. "
        "Не используй кодовые блоки."
    )

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": DEEPSEEK_VISION_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.2,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=180) as r:
            txt = await r.text()
            if r.status != 200:
                raise RuntimeError(f"DeepSeek vision error {r.status}: {txt}")
            data = await r.json()

    content = data["choices"][0]["message"]["content"]
    return _clean_output(content)
