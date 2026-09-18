FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn httpx

COPY scripts/reference_plugin_server.py /app/main.py

ENV PORT=8081
ENV PYTHONUNBUFFERED=1
ENV PLUGIN_WEBHOOK_SECRET="reference_test_secret_key_32_bytes_len"

EXPOSE 8081

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]
