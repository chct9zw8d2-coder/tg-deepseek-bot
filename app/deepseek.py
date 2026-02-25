import os
import httpx
from typing import List, Dict, Optional

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "Ты полезный ассистент. Отвечай коротко и по делу."
)

# Жесткий промпт, чтобы НЕ было LaTeX/слешей/кавычек-артефактов
HOMEWORK_SYSTEM_PROMPT = os.getenv(
    "HOMEWORK_SYSTEM_PROMPT",
    (
        "Ты решаешь школьные/студенческие задачи.\n"
        "ВАЖНО:\n"
        "- НЕ используй LaTeX.\n"
        "- НЕ используй символы: \\[ \\] \\( \\) и обратные слеши.\n"
        "- Пиши обычным текстом.\n"
        "- Сначала 'Условие:' (аккуратно перепиши), затем 'Решение:' пошагово, затем 'Ответ:'.\n"
        "- Если в тексте с фото есть мусор/неясности — выбери самый вероятный вариант и пометь 'Предположение: ...'.\n"
    )
)

async def _call_deepseek(messages: List[Dict[str, str]], temperature: float = 0.4) -> str:
    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY."

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": temperature,
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


# Совместимость со старым кодом: просто ответ на любой текст
async def ask_deepseek(user_text: str, system_prompt: Optional[str] = None) -> str:
    sys_prompt = (system_prompt or DEFAULT_SYSTEM_PROMPT).strip()
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]
    return await _call_deepseek(messages, temperature=0.6)


# Специально для решения задач с фото (после OCR)
async def solve_homework_from_text(ocr_text: str) -> str:
    messages = [
        {"role": "system", "content": HOMEWORK_SYSTEM_PROMPT},
        {"role": "user", "content": f"Текст с фото:\n{ocr_text}"},
    ]
    return await _call_deepseek(messages, temperature=0.2)
