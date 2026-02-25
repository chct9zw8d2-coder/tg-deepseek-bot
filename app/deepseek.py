import os
import re
import httpx
from typing import List, Dict, Optional


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


# ---------------------------
# ОЧИСТКА LaTeX И МУСОРА
# ---------------------------
def clean_math_text(text: str) -> str:
    if not text:
        return text

    # убрать LaTeX скобки
    text = text.replace("\\(", "")
    text = text.replace("\\)", "")
    text = text.replace("\\[", "")
    text = text.replace("\\]", "")

    # frac -> обычная дробь
    text = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"\1/\2", text)

    # убрать команды latex
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)

    # убрать обратные слеши
    text = text.replace("\\", "")

    # убрать двойные пробелы
    text = re.sub(r"[ ]{2,}", " ", text)

    return text.strip()


# ---------------------------
# CALL API
# ---------------------------
async def _call_deepseek(messages: List[Dict[str, str]], temperature: float = 0.4) -> str:

    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY"

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
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        text = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        # ВАЖНО: очищаем ответ
        return clean_math_text(text)

    except Exception as e:
        return f"Ошибка DeepSeek: {e}"


# ---------------------------
# ОБЫЧНЫЙ ВОПРОС
# ---------------------------
async def ask_deepseek(user_text: str, system_prompt: Optional[str] = None) -> str:

    sys_prompt = (
        system_prompt
        or "Отвечай обычным текстом. Не используй LaTeX и обратные слеши."
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]

    return await _call_deepseek(messages, temperature=0.6)


# ---------------------------
# РЕШЕНИЕ ЗАДАЧ
# ---------------------------
async def solve_homework_from_text(ocr_text: str) -> str:

    system_prompt = (
        "Реши задачу.\n"
        "Пиши обычным текстом.\n"
        "Не используй LaTeX.\n"
        "Не используй \\frac, \\(, \\).\n\n"
        "Формат:\n"
        "Условие:\n"
        "Решение:\n"
        "Ответ:"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": ocr_text},
    ]

    return await _call_deepseek(messages, temperature=0.2)
