# TG DeepSeek Bot (Railway-ready)

## Env vars (Railway -> Variables)
- BOT_TOKEN
- WEBHOOK_URL  (https://<app>.up.railway.app/webhook)
- DATABASE_URL (Railway Postgres variable)
- DEEPSEEK_API_KEY
- (optional) BOT_USERNAME (for referral links)
- (optional) ADMIN_IDS (comma/space separated Telegram user ids)

DeepSeek:
- DEEPSEEK_BASE_URL (default https://api.deepseek.com)
- DEEPSEEK_TEXT_MODEL (default deepseek-chat)

Optional vision endpoint (OpenAI-compatible):
- DEEPSEEK_VISION_BASE_URL
- DEEPSEEK_VISION_MODEL
- DEEPSEEK_VISION_API_KEY

## Run locally
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BOT_TOKEN=...
export WEBHOOK_URL=https://example.com/webhook
export DATABASE_URL=postgresql://...
export DEEPSEEK_API_KEY=...
uvicorn app.main:app --reload
