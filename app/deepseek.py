import os
import httpx

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()

# DeepSeek часто OpenAI-compatible. Делаем гибко:
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Ты полезный ассистент. Отвечай коротко и по делу, на языке пользователя."
)

class DeepSeekError(Exception):
    pass


async def ask_deepseek(user_text: str) -> str:
    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY в переменных Railway."

    # OpenAI-compatible endpoint (у DeepSeek обычно так)
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        # OpenAI-style response: choices[0].message.content
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        ).strip()

        if not content:
            return "⚠️ DeepSeek вернул пустой ответ."

        return content

    except httpx.HTTPStatusError as e:
        # покажем текст ошибки (коротко)
        try:
            err = e.response.json()
        except Exception:
            err = e.response.text
        return f"❌ Ошибка DeepSeek: {e.response.status_code} — {err}"

    except Exception as e:
        return f"❌ Ошибка запроса к DeepSeek: {e}"
