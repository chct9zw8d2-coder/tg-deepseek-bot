import os
import base64
import re
import httpx
from typing import Any, Dict, List, Optional


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

DEEPSEEK_TEXT_MODEL = os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-chat").strip()
DEEPSEEK_VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2").strip()


def _latex_to_text(s: str) -> str:
    """Превращает частый LaTeX в нормальный текст."""
    if not s:
        return s

    s = s.replace("```", "")
    s = s.replace("\\(", "").replace("\\)", "")
    s = s.replace("\\[", "").replace("\\]", "")
    s = s.replace("$", "")

    for _ in range(3):
        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", s)

    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", s)

    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)

    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = s.replace("\\approx", "~")
    s = s.replace("\\le", "<=").replace("\\ge", ">=")
    s = s.replace("\\to", "->").replace("\\pm", "±")
    s = s.replace("\\pi", "pi")

    s = re.sub(r"\^\{(\d+)\}", r"^\1", s)
    s = re.sub(r"\^\{([^}]+)\}", r"^(\1)", s)

    s = re.sub(r"_\{(\d+)\}", r"_\1", s)
    s = re.sub(r"_\{([^}]+)\}", r"_(\1)", s)

    s = s.replace("\\left", "").replace("\\right", "")
    s = re.sub(r"\\[,;:!]", " ", s)
    s = re.sub(r"\\[a-zA-Z]+", "", s)
    s = s.replace("\\", "")

    s = s.replace("\r", "")
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()


async def _call_deepseek(payload: Dict[str, Any]) -> str:
    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY."

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload, headers=headers)
            # если модель не поддерживается/не найдена — тут будет 4xx, покажем текст
            if r.status_code >= 400:
                return f"❌ DeepSeek {r.status_code}: {r.text}"

            data = r.json()

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _latex_to_text(text)

    except Exception as e:
        return f"❌ Ошибка DeepSeek: {e}"


async def ask_text(user_text: str) -> str:
    system_prompt = (
        "Отвечай обычным текстом. "
        "Не используй LaTeX, не используй обратные слеши. "
        "Если нужна математика — пиши так: 16/3, sqrt(2), x^2."
    )
    payload = {
        "model": DEEPSEEK_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.5,
    }
    return await _call_deepseek(payload)


async def solve_homework_vision(image_bytes: bytes, extra_text: Optional[str] = None) -> str:
    """
    Vision: отправляем картинку в OpenAI-совместимом формате content=[text,image_url].
    Если модель не умеет — вернётся понятная ошибка.
    """
    prompt = (extra_text or "").strip()
    if not prompt:
        prompt = "Реши задачу на фото."

    system_prompt = (
        "Ты решаешь задачи с фото.\n"
        "Пиши только обычным текстом.\n"
        "Запрещено: LaTeX, \\frac, \\( \\), \\[ \\], обратные слеши.\n\n"
        "Формат ответа:\n"
        "Условие:\n"
        "...\n\n"
        "Решение:\n"
        "пошагово\n\n"
        "Ответ:\n"
        "одной строкой\n"
    )

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64}"

    payload = {
        "model": DEEPSEEK_VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 1800,
    }

    return await _call_deepseek(payload)
