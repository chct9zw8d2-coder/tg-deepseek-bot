from openai import OpenAI
from app.config import settings

client = OpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)

async def ask_deepseek(prompt, reason=False):
    model = settings.DEEPSEEK_REASON_MODEL if reason else settings.DEEPSEEK_TEXT_MODEL
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "Ты полезный ассистент."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content
