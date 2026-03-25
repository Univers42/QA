FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        jq \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/prismatica-qa

COPY pyproject.toml README.md ./
COPY prismatica_qa ./prismatica_qa

RUN pip install --upgrade pip \
    && pip install .

WORKDIR /workspace

ENTRYPOINT ["python", "-m", "prismatica_qa"]
