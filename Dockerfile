FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway выдаёт порт в переменной окружения PORT.
# В exec-форме CMD переменные не подставляются, поэтому запускаем через sh -c.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
