import base64
import httpx
from app.config import settings


BASE_URL = settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com"


async def ask_deepseek(prompt: str) -> str:
    url = f"{BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.DEEPSEEK_TEXT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты помощник по учебе. Отвечай понятно и структурированно. "
                    "НЕ используй LaTeX. Пиши обычным текстом."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.2
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, headers=headers, json=payload)

    data = response.json()

    if "choices" not in data:
        return f"Ошибка API: {data}"

    return data["choices"][0]["message"]["content"]


async def ask_deepseek_vision(image_bytes: bytes, prompt: str) -> str:
    url = f"{BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    image_base64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": settings.DEEPSEEK_VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты помощник по учебе. "
                    "Распознавай текст с фото и решай задачу. "
                    "НЕ используй LaTeX. Пиши обычным текстом."
                )
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
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.2
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, headers=headers, json=payload)

    data = response.json()

    if "choices" not in data:
        return f"Ошибка Vision API: {data}"

    return data["choices"][0]["message"]["content"]
