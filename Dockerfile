FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=0

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app
WORKDIR /app/app

# Fly 가 넘겨주는 $PORT 준수
ENV PORT=8080
CMD ["gunicorn", "server:app", "-k", "gevent", "-w", "2", "-b", "0.0.0.0:8080"]
