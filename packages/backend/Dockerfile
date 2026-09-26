FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libxmlsec1-openssl \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip && pip install uv

COPY pyproject.toml README.md ./
RUN uv pip install --system -e .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "titan_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
