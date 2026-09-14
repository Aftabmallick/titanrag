.PHONY: help up down quickstart full obs logs clean migrate test lint format health

COMPOSE_FILE = packages/infra/docker-compose.yml

help:
	@echo "TitanRAG Developer CLI Commands:"
	@echo "  make quickstart   - Start lightweight PostgreSQL 16 + Qdrant + FastAPI (<2 min)"
	@echo "  make up           - Start default stack (PG, Redis, Qdrant, MinIO, LiteLLM, FastAPI, Celery)"
	@echo "  make obs          - Start observability stack (Prometheus, Grafana, Jaeger)"
	@echo "  make full         - Start all services (Default + Observability + Heavy Worker + Frontend)"
	@echo "  make down         - Stop all running containers"
	@echo "  make clean        - Stop containers and purge persistent volumes"
	@echo "  make logs         - Stream container logs"
	@echo "  make migrate      - Run Alembic database migrations"
	@echo "  make test         - Run test suite across packages"
	@echo "  make lint         - Check linting and code formatting"
	@echo "  make format       - Automatically fix linting and format code"
	@echo "  make health       - Query the deep health readiness endpoint"

quickstart:
	docker compose -f $(COMPOSE_FILE) --profile quickstart up -d --wait

up:
	docker compose -f $(COMPOSE_FILE) --profile default up -d

obs:
	docker compose -f $(COMPOSE_FILE) --profile observability up -d

full:
	docker compose -f $(COMPOSE_FILE) --profile full up -d

down:
	docker compose -f $(COMPOSE_FILE) --profile full down

clean:
	docker compose -f $(COMPOSE_FILE) --profile full down -v

logs:
	docker compose -f $(COMPOSE_FILE) logs -f

migrate:
	cd packages/backend && uv run alembic upgrade head

test:
	uv run pytest -v

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

health:
	@curl -s http://localhost:8000/health/ready | python3 -m json.tool || echo "Service unreachable"
