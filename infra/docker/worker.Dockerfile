# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend-requirements.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r backend-requirements.txt

COPY backend ./backend

CMD ["celery", "-A", "backend.workers.celery_app:celery_app", "worker", "--loglevel=INFO"]
