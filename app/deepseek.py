import os
import re
import base64
import aiohttp

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = (os.getenv("DEEPSEEK_BASE_URL", "") or "https://api.deepseek.com").rstrip("/")
DEEPSEEK_TEXT_MODEL = os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-chat")
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2")

if not DEEPSEEK_API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY is not set")

_http: aiohttp.ClientSession | None = None


def _sanitize(text: str) -> str:
    # убираем частые мусорные LaTeX-обёртки, которые портят вид в Telegram
    text = text.replace("\\[", "").replace("\\]", "")
    text = text.replace("\\(", "").replace("\\)", "")
    # иногда модель вставляет лишние обратные слэши
    text = re.sub(r"\\{2,}", r"\\", text)
    return text.strip()


async def _session() -> aiohttp.ClientSession:
    global _http
    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))
    return _http


async def close_http():
    global _http
    if _http and not _http.closed:
        await _http.close()
    _http = None


async def ask_deepseek_text(prompt: str) -> str:
    s = await _session()
    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"

    payload = {
        "model": DEEPSEEK_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": "Отвечай кратко, понятно, без LaTeX-скобок \\(\\) и \\[\\]."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    async with s.post(url, json=payload, headers=headers) as r:
        data = await r.json(content_type=None)
        if r.status >= 400:
            raise RuntimeError(f"DeepSeek TEXT HTTP {r.status}: {data}")
        text = data["choices"][0]["message"]["content"]
        return _sanitize(text)


async def ask_deepseek_vision(image_bytes: bytes, prompt: str) -> str:
    s = await _session()
    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{b64}"

    payload = {
        "model": DEEPSEEK_VISION_MODEL,
        "messages": [
            {"role": "system", "content": "Отвечай понятно, структурировано, без LaTeX-скобок."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        "temperature": 0.2,
    }

    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    async with s.post(url, json=payload, headers=headers) as r:
        data = await r.json(content_type=None)
        if r.status >= 400:
            raise RuntimeError(f"DeepSeek VISION HTTP {r.status}: {data}")
        text = data["choices"][0]["message"]["content"]
        return _sanitize(text)
