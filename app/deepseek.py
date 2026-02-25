import os
import base64
import re
import httpx

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

# Текстовая модель (обычные вопросы)
DEEPSEEK_TEXT_MODEL = os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-chat").strip()

# Vision-модель (для фото). Поставил дефолт deepseek-vl2 — если недоступна, API вернет ошибку.
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2").strip()

SYSTEM_PROMPT_TEXT = os.getenv(
    "SYSTEM_PROMPT_TEXT",
    "Ты полезный ассистент для учебы. Отвечай понятно, структурировано и без воды. "
    "ВАЖНО: не используй LaTeX-разметку (никаких \\( \\) \\[ \\] и т.п.). "
    "Формулы пиши обычным текстом, можно с символами: + - * / ^ sqrt()."
)

SYSTEM_PROMPT_VISION = os.getenv(
    "SYSTEM_PROMPT_VISION",
    "Ты помощник по домашним заданиям. Тебе пришлют фото задачи. "
    "Сначала аккуратно перепиши условие (обычным текстом), затем реши по шагам и дай финальный ответ. "
    "ВАЖНО: не используй LaTeX-разметку (никаких \\( \\) \\[ \\]). "
    "Формулы пиши обычным текстом, можно с символами: + - * / ^ sqrt(). "
    "Если на фото несколько задач — решай все по порядку."
)

def _sanitize_answer(text: str) -> str:
    """Убираем LaTeX-огрызки и мусор, чтобы Telegram не превращался в кашу."""
    if not text:
        return "⚠️ Пустой ответ."

    # Убираем типичные LaTeX-обертки
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\[", "").replace("\\]", "")

    # Часто модель присылает экранированные слэши
    text = text.replace("\\{", "{").replace("\\}", "}")
    text = text.replace("\\_", "_")

    # Убираем повторяющиеся пустые строки
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text


async def _post_chat(payload: dict) -> str:
    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY."

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return _sanitize_answer(content)

    except httpx.HTTPStatusError as e:
        # Покажем тело ответа — это поможет понять, доступна ли vision модель
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        return f"❌ DeepSeek HTTP {e.response.status_code}: {body or str(e)}"

    except Exception as e:
        return f"❌ Ошибка DeepSeek: {e}"


async def ask_text(user_text: str) -> str:
    payload = {
        "model": DEEPSEEK_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_TEXT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.4,
    }
    return await _post_chat(payload)


async def ask_vision(image_bytes: bytes, user_text: str = "") -> str:
    """
    OpenAI-compatible multimodal:
    messages: [{role:'user', content:[{type:'text', text:'...'}, {type:'image_url', image_url:{url:'data:image/jpeg;base64,...'}}]}]
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    prompt = user_text.strip() or "Реши задачу на фото."

    payload = {
        "model": DEEPSEEK_VISION_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_VISION},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 1500,
    }

    return await _post_chat(payload)
