import os
import re
import httpx
from typing import List, Dict, Optional


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")


def _latex_to_text(s: str) -> str:
    if not s:
        return s

    # Убрать типовые latex-обёртки
    s = s.replace("```", "")
    s = s.replace("\\(", "").replace("\\)", "")
    s = s.replace("\\[", "").replace("\\]", "")
    s = s.replace("$", "")

    # frac -> a/b (повторяем несколько раз на случай вложенности)
    for _ in range(3):
        s = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"\1/\2", s)

    # sqrt -> sqrt(x)
    s = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", s)

    # text{...} -> ...
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)

    # cdot, times -> *
    s = s.replace("\\cdot", "*").replace("\\times", "*")

    # approx -> ~
    s = s.replace("\\approx", "~")

    # <= >=
    s = s.replace("\\le", "<=").replace("\\ge", ">=")

    # ->, pm
    s = s.replace("\\to", "->").replace("\\pm", "±")

    # pi
    s = s.replace("\\pi", "pi")

    # степени: x^{2} -> x^2, x^{n+1} -> x^(n+1)
    s = re.sub(r"\^\{(\d+)\}", r"^\1", s)
    s = re.sub(r"\^\{([^}]+)\}", r"^(\1)", s)

    # нижние индексы: a_{1} -> a_1, a_{n+1} -> a_(n+1)
    s = re.sub(r"_\{(\d+)\}", r"_\1", s)
    s = re.sub(r"_\{([^}]+)\}", r"_(\1)", s)

    # убрать \left \right
    s = s.replace("\\left", "").replace("\\right", "")

    # убрать \, \; \: и прочие пробельные команды
    s = re.sub(r"\\[,;:!]", " ", s)

    # убрать любые оставшиеся latex-команды вида \something
    s = re.sub(r"\\[a-zA-Z]+", "", s)

    # убрать оставшиеся обратные слеши
    s = s.replace("\\", "")

    # подчистить пробелы/переводы
    s = s.replace("\r", "")
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    # немного “очеловечим”
    s = s.strip()
    return s


async def _call_deepseek(messages: List[Dict[str, str]], temperature: float = 0.4) -> str:
    if not DEEPSEEK_API_KEY:
        return "❌ Не задан DEEPSEEK_API_KEY"

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    payload = {"model": DEEPSEEK_MODEL, "messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _latex_to_text(text)

    except Exception as e:
        return f"Ошибка DeepSeek: {e}"


async def ask_deepseek(user_text: str, system_prompt: Optional[str] = None) -> str:
    sys_prompt = system_prompt or (
        "Отвечай обычным текстом. "
        "Не используй LaTeX, не используй обратные слеши. "
        "Если нужна математика — пиши как 16/3, sqrt(2), x^2."
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_text},
    ]
    return await _call_deepseek(messages, temperature=0.6)


async def solve_homework_from_text(ocr_text: str) -> str:
    system_prompt = (
        "Ты решаешь задачи.\n"
        "Пиши только обычным текстом.\n"
        "Запрещено: LaTeX, \\frac, \\( \\), \\[ \\], обратные слеши.\n\n"
        "Формат ответа строго такой:\n"
        "Условие:\n"
        "...\n\n"
        "Решение:\n"
        "пошагово\n\n"
        "Ответ:\n"
        "одной строкой\n\n"
        "Если OCR-условие неидеально — уточни предположение одной строкой."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Текст с фото:\n{ocr_text}"},
    ]
    return await _call_deepseek(messages, temperature=0.2)
