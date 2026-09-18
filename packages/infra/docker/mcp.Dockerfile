FROM python:3.12-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Install uv for fast package installations
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY packages/sdk/ packages/sdk/
COPY packages/mcp/ packages/mcp/

# Install dependencies into system environment
RUN uv pip install --system packages/sdk/ packages/mcp/

ENV PYTHONUNBUFFERED=1
ENV TITANRAG_BASE_URL="http://backend:8000"

EXPOSE 8080

ENTRYPOINT ["titan-mcp"]
CMD ["--transport", "stdio"]
