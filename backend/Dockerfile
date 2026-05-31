# API server image — FastAPI on uvicorn (ECS Fargate, CPU).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg / building wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps. requirements.txt is the S0-A scaffold manifest; when
# S0-B's pyproject.toml lands the build can switch to poetry.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Application source (the `app` package lives under backend/app).
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

# Non-root runtime.
RUN useradd --create-home --uid 1000 appuser
USER 1000:1000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
