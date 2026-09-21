# Contributing to TitanRAG Enterprise

Welcome to the TitanRAG contributor community! We are building a production-grade, multi-tenant multimodal Retrieval-Augmented Generation platform.

---

## 1. Development Workflow & Standards

### Python Standards
- Python 3.12+ managed via `uv`
- Formatting & Linting: `ruff check .` and `ruff format .`
- Strict Static Typing: `mypy --strict` on all backend and SDK packages
- No untyped public functions or loose `Any` return annotations

### Frontend Standards
- Next.js 14+ App Router, TypeScript 5+
- ESLint + Prettier
- Accessible components (WCAG 2.1 AA compliance)

---

## 2. Local Development Without Full Docker (`make dev-local`)

To develop locally without running the entire 14-container stack while preserving PostgreSQL Row-Level Security (RLS) parity:

```bash
# 1. Start lightweight containerized PostgreSQL 16 (RLS enabled) + Redis
make dev-db

# 2. Run database migrations
make migrate

# 3. Start FastAPI Backend in hot-reload mode
make dev-backend

# 4. In a second terminal, start Next.js UI
make dev-frontend
```

---

## 3. Pull Request Requirements

Every PR must pass automated CI checks:
1. **Lint & Type Check**: `ruff` + `mypy --strict`
2. **Unit & Integration Tests**: `pytest` across all modified packages
3. **Expand-Contract Schema Safety**: `python scripts/check_migration_safety.py`
4. **OpenAPI Breaking Change Detection**: `python scripts/verify_openapi_contract.py`
5. **No plaintext credentials** or unencrypted secrets committed.
