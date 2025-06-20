FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=0

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app

ENV PORT=8080
CMD ["gunicorn", "--preload", "app:app", "-k", "gevent", "-w", "2", "-b", "0.0.0.0:8080"]
