from __future__ import annotations
import base64
import httpx
from app.config import settings

def _clean_answer(text: str) -> str:
    # Make it nice for Telegram: remove leading blockquote markers and code fences
    lines = []
    in_fence = False
    for ln in (text or "").splitlines():
        s = ln.rstrip()
        if s.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if s.lstrip().startswith(">"):
            s = s.lstrip()[1:].lstrip()
        lines.append(s)
    out = "\n".join(lines).strip()
    return out

async def _chat_completion(messages, *, base_url: str, api_key: str, model: str, timeout: float = 60.0) -> str:
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"model": model, "messages": messages, "temperature": 0.3}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]

async def answer_any_question(question: str) -> str:
    messages = [
        {"role": "system", "content": "Ты полезный ассистент. Отвечай подробно, понятно, структурировано. Не используй блок-цитаты '>' и не используй тройные кавычки ```."},
        {"role": "user", "content": question},
    ]
    text = await _chat_completion(messages, base_url=settings.DEEPSEEK_BASE_URL, api_key=settings.DEEPSEEK_API_KEY, model=settings.DEEPSEEK_TEXT_MODEL)
    return _clean_answer(text)

async def solve_homework_text(task: str) -> str:
    messages = [
        {"role": "system", "content": "Ты репетитор. Помоги решить домашнее задание: объясняй шаги, формулы, но пиши компактно. В конце выдели 'Ответ: ...'. Не используй '>' и ```."},
        {"role": "user", "content": task},
    ]
    text = await _chat_completion(messages, base_url=settings.DEEPSEEK_BASE_URL, api_key=settings.DEEPSEEK_API_KEY, model=settings.DEEPSEEK_TEXT_MODEL)
    return _clean_answer(text)

async def solve_homework_image(image_bytes: bytes, ocr_text: str) -> str:
    # If user has a vision endpoint configured, use it; otherwise use OCR text.
    if settings.DEEPSEEK_VISION_BASE_URL and settings.DEEPSEEK_VISION_MODEL:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_url = f"data:image/jpeg;base64,{b64}"
        messages = [
            {"role": "system", "content": "Ты решаешь задачи по фото. Сначала аккуратно перепиши условие, затем реши, затем отдельно дай финальный ответ. Не используй '>' и ```."},
            {"role": "user", "content": [
                {"type": "text", "text": "Реши задачу с изображения. Сначала перепиши условие (без ошибок), потом решение, потом финальный ответ."},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]},
        ]
        text = await _chat_completion(
            messages,
            base_url=settings.DEEPSEEK_VISION_BASE_URL,
            api_key=(settings.DEEPSEEK_VISION_API_KEY or settings.DEEPSEEK_API_KEY),
            model=settings.DEEPSEEK_VISION_MODEL,
            timeout=90.0
        )
        return _clean_answer(text)

    # OCR fallback
    prompt = f"""Вот текст, распознанный с фото (может быть с ошибками). 
1) Аккуратно восстанови условие задачи без мусора.
2) Реши задачу подробно.
3) В конце отдельно напиши строку: Ответ: ...
Текст:
{ocr_text}
"""
    messages = [
        {"role": "system", "content": "Ты решаешь задачи по фото. Исправляй ошибки OCR. Не используй '>' и ```."},
        {"role": "user", "content": prompt},
    ]
    text = await _chat_completion(messages, base_url=settings.DEEPSEEK_BASE_URL, api_key=settings.DEEPSEEK_API_KEY, model=settings.DEEPSEEK_TEXT_MODEL, timeout=90.0)
    return _clean_answer(text)
