# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Установим системные зависимости по минимуму
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Установим зависимости проекта
COPY requirements.txt ./
# requirements-dev.txt может отсутствовать
COPY requirements-dev.txt ./ 2>/dev/null || true
RUN pip install --upgrade pip \
 && pip install -r requirements.txt \
 && if [ -f requirements-dev.txt ]; then pip install -r requirements-dev.txt; fi

# Копируем исходники
COPY . .

# Приложение слушает 45469
EXPOSE 45469

# Запуск сервера
CMD ["uvicorn", "app.server.main:app", "--host", "0.0.0.0", "--port", "45469"]
