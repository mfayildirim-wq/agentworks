# Build-Context = Repo-Root (Backend braucht agent-runtime als Pfad-Dependency).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --upgrade pip

# agent-runtime zuerst (eigene Dependency von backend), dann backend.
COPY agent-runtime ./agent-runtime
COPY backend ./backend
RUN pip install ./agent-runtime ./backend

WORKDIR /app/backend

EXPOSE 8000

# Default = API. Worker/Cron überschreiben das command in der Compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
