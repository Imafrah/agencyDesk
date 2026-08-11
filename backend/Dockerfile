FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SEED_ON_BOOT=true

CMD ["sh", "-c", "alembic upgrade head && ( [ \"$SEED_ON_BOOT\" = \"true\" ] && python seed.py || true ) && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
