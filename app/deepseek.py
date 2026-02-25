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

# глобальная http сессия
_http: aiohttp.ClientSession | None = None


# очистка мусорного latex
def _sanitize(text: str) -> str:
    text = text.replace("\\[", "").replace("\\]", "")
    text = text.replace("\\(", "").replace("\\)", "")
    text = re.sub(r"\\{2,}", r"\\", text)
    return text.strip()


# получить http session
async def _get_session() -> aiohttp.ClientSession:
    global _http

    if _http is None or _http.closed:
        _http = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=180)
        )

    return _http


# ВАЖНО: эта функция нужна main.py
async def close_http():
    global _http

    if _http and not _http.closed:
        await _http.close()

    _http = None


# TEXT запрос
async def ask_deepseek_text(prompt: str) -> str:
    session = await _get_session()

    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"

    payload = {
        "model": DEEPSEEK_TEXT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Отвечай понятно, без LaTeX-скобок \\(\\) и \\[\\]"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    async with session.post(url, json=payload, headers=headers) as resp:

        data = await resp.json(content_type=None)

        if resp.status >= 400:
            raise RuntimeError(f"DeepSeek TEXT error: {data}")

        text = data["choices"][0]["message"]["content"]

        return _sanitize(text)


# VISION запрос
async def ask_deepseek_vision(image_bytes: bytes, prompt: str) -> str:

    session = await _get_session()

    url = f"{DEEPSEEK_BASE_URL}/v1/chat/completions"

    b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": DEEPSEEK_VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "Решай задания с фото понятно и без LaTeX-скобок"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    async with session.post(url, json=payload, headers=headers) as resp:

        data = await resp.json(content_type=None)

        if resp.status >= 400:
            raise RuntimeError(f"DeepSeek VISION error: {data}")

        text = data["choices"][0]["message"]["content"]

        return _sanitize(text)
