import os
import base64
import aiohttp


def _env(name: str, default: str | None = None) -> str | None:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    return v.strip()


DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_TEXT_MODEL = _env("DEEPSEEK_TEXT_MODEL", "deepseek-chat")
DEEPSEEK_VISION_MODEL = _env("DEEPSEEK_VISION_MODEL", "deepseek-vl2")


class DeepSeekError(Exception):
    pass


def _clean_for_telegram(text: str) -> str:
    # Убираем "кривые" latex-обертки, которые портят вид в Telegram
    for bad in ["\\(", "\\)", "\\[", "\\]"]:
        text = text.replace(bad, "")
    # иногда модель ставит лишние обратные слэши
    text = text.replace("\\\\", "\\")
    return text.strip()


async def _post_chat(messages, model: str) -> str:
    if not DEEPSEEK_API_KEY:
        raise DeepSeekError("DEEPSEEK_API_KEY не задан в переменных окружения")

    url = f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    timeout = aiohttp.ClientTimeout(total=120)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            data = await resp.json(content_type=None)

            if resp.status >= 400:
                raise DeepSeekError(f"DeepSeek API error {resp.status}: {data}")

            try:
                text = data["choices"][0]["message"]["content"]
            except Exception:
                raise DeepSeekError(f"Unexpected response: {data}")

            return _clean_for_telegram(text)


# ============ PUBLIC API ============

async def ask_text(user_text: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "Ты учебный помощник. Отвечай по-русски, структурируй решение."
                " Не используй LaTeX-обертки вида \\( \\) или \\[ \\]."
            )
        },
        {"role": "user", "content": user_text}
    ]
    return await _post_chat(messages, model=DEEPSEEK_TEXT_MODEL)


async def ask_vision(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    messages = [
        {
            "role": "system",
            "content": (
                "Ты решаешь задачи по фото. Сначала аккуратно перепиши условие (как ты его понял), "
                "потом дай решение по шагам, затем итоговый ответ. "
                "Не используй LaTeX-обертки вида \\( \\) или \\[ \\]."
            )
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Реши задачу с изображения. Пиши понятным русским текстом."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        },
    ]

    return await _post_chat(messages, model=DEEPSEEK_VISION_MODEL)
