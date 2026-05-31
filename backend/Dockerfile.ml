# GPU ML worker image — Celery worker for the ml_inference queue on EC2 G4dn.
# Bases on an NVIDIA CUDA runtime image (GPU instance type is irreversible at
# infrastructure provisioning time — §1.8).
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Python 3.11 + build deps on top of the CUDA base.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11 python3.11-dev python3-pip libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 1000 mluser
USER 1000:1000

CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", \
     "-Q", "ml_inference", "--concurrency=1"]
