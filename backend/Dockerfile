FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY backend /app/backend
RUN pip install --no-cache-dir "/app/backend[ml]"
COPY ml /app/ml
RUN groupadd --system azari \
    && useradd --system --gid azari --home-dir /nonexistent --no-create-home azari \
    && chown -R azari:azari /app

USER azari

EXPOSE 8000
CMD ["sh", "-c", "alembic -c /app/backend/alembic.ini upgrade head && python -m backend.app.db.bootstrap && python -m backend.scripts.demo_database ensure && exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
