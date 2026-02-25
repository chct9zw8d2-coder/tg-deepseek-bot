import os
import base64
import httpx

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

TEXT_MODEL = os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-chat")
VISION_MODEL = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2")


async def ask_deepseek_text(prompt: str) -> str:
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    json = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=json)

    if resp.status_code != 200:
        return f"DeepSeek error: {resp.text}"

    data = resp.json()
    return data["choices"][0]["message"]["content"]


async def ask_deepseek_vision(image_bytes: bytes, prompt: str) -> str:
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    image_base64 = base64.b64encode(image_bytes).decode()

    json = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=json)

    if resp.status_code != 200:
        return f"DeepSeek vision error: {resp.text}"

    data = resp.json()
    return data["choices"][0]["message"]["content"]
