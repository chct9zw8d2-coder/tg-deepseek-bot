import os
import httpx

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_HOMEWORK = os.getenv(
    "SYSTEM_HOMEWORK",
    "Ты опытный преподаватель. Решай задачи пошагово, объясняй понятно и подробно."
)

SYSTEM_GENERAL = os.getenv(
    "SYSTEM_GENERAL",
    "Ты полезный ассистент. Отвечай широко, структурно и по делу."
)

SYSTEM_PHOTO = os.getenv(
    "SYSTEM_PHOTO",
    "Ты опытный преподаватель. Пользователь прислал текст, распознанный с фото. Реши задачу пошагово."
)

async def ask_deepseek(user_text: str, system_prompt: str) -> str:
    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY."

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "⚠️ Пустой ответ.")
        )

    except Exception as e:
        return f"❌ Ошибка DeepSeek: {e}"
