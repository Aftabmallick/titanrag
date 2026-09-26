import os
import secrets
import warnings

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sentinel value used to detect unconfigured secrets at startup
_DEV_SECRET_SENTINEL = "__auto_generated__"


def _generate_dev_secret(label: str) -> str:
    """Generate a cryptographically secure random secret for development mode."""
    token = secrets.token_urlsafe(48)
    warnings.warn(
        f"[TitanRAG] {label} was auto-generated for development. "
        f"Set it explicitly via environment variable or .env for production.",
        stacklevel=2,
    )
    return token


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),  # .env.local takes priority over .env
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # =========================================================================
    # Core System
    # =========================================================================
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    QUICKSTART_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "TitanRAG"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "TitanRAG Enterprise Core"

    # =========================================================================
    # Security & JWT
    # =========================================================================
    SECRET_KEY: str = _DEV_SECRET_SENTINEL
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_PRIVATE_KEY: str | None = None
    JWT_PUBLIC_KEY: str | None = None

    # =========================================================================
    # OAuth2 Providers
    # =========================================================================
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None

    # =========================================================================
    # SCIM 2.0
    # =========================================================================
    SCIM_BEARER_TOKEN: str = _DEV_SECRET_SENTINEL

    # =========================================================================
    # Brute-Force Protection
    # =========================================================================
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_DURATION_SECONDS: int = 900  # 15 minutes

    # =========================================================================
    # Rate Limiting & FinOps Compute Units (CU)
    # =========================================================================
    RATE_LIMIT_PER_MINUTE_ADMIN: int = 100000
    RATE_LIMIT_PER_MINUTE_MEMBER: int = 50000
    RATE_LIMIT_PER_MINUTE_ANONYMOUS: int = 10000
    RATE_LIMIT_DISABLED: bool = False  # Set True in test environments only
    DEFAULT_MONTHLY_CU_QUOTA: int = 10000

    # =========================================================================
    # CU Cost Table (weighted compute unit costs per operation)
    # =========================================================================
    CU_COST_TEXT_QUERY: int = 1
    CU_COST_OCR_PAGE: int = 3
    CU_COST_BATCHED_CONTEXT: int = 5
    CU_COST_COLPALI_PAGE: int = 10
    CU_TOKENS_PER_UNIT: int = 1000  # 1 CU per N tokens

    # =========================================================================
    # Quota Defaults (overridable per tenant/plan)
    # =========================================================================
    DEFAULT_MAX_STORAGE_BYTES: int = 10 * 1024 * 1024 * 1024  # 10GB
    DEFAULT_MAX_DOCUMENTS: int = 10000
    DEFAULT_MAX_QUERIES_PER_DAY: int = 5000

    # =========================================================================
    # PostgreSQL
    # =========================================================================
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_dev_password"
    POSTGRES_DB: str = "titanrag"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str | None = None
    SYNC_DATABASE_URL: str | None = None

    # Connection Pool
    DB_POOL_SIZE: int = 50
    DB_MAX_OVERFLOW: int = 30
    DB_POOL_TIMEOUT_SECONDS: int = 60
    DB_POOL_RECYCLE_SECONDS: int = 3600

    # =========================================================================
    # Redis
    # =========================================================================
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 20
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # =========================================================================
    # Qdrant Vector Engine
    # =========================================================================
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # Qdrant Collections & Tuning
    QDRANT_COLLECTION_NAME: str = "titan_chunks"
    QDRANT_COLPALI_COLLECTION_NAME: str = "titan_colpali_visual"
    QDRANT_DENSE_VECTOR_SIZE: int = 1536
    QDRANT_COLPALI_VECTOR_SIZE: int = 128
    QDRANT_HNSW_M: int = 16
    QDRANT_HNSW_EF_CONSTRUCT: int = 128
    QDRANT_QUANTILE: float = 0.99
    QDRANT_TENANT_MAX_CONCURRENT: int = 5
    QDRANT_SEMAPHORE_TTL_SECONDS: int = 600

    # =========================================================================
    # MinIO Object Storage
    # =========================================================================
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_BUCKET: str = "titanrag-documents"
    MINIO_USE_SSL: bool = False

    # =========================================================================
    # LiteLLM & Models
    # =========================================================================
    LITELLM_HOST: str = "localhost"
    LITELLM_PORT: int = 4000
    LITELLM_URL: str = "http://localhost:4000"
    LITELLM_MASTER_KEY: str = _DEV_SECRET_SENTINEL
    DEFAULT_CHAT_MODEL: str = "deepseek-ai/deepseek-v4-flash-0731"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    COHERE_API_KEY: str | None = None
    NVIDIA_API_KEY: str | None = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "deepseek-ai/deepseek-v4-flash-0731"

    # =========================================================================
    # Reranker Configuration
    # =========================================================================
    RERANKER_TIMEOUT_MS: int = 400
    COHERE_RERANK_URL: str = "https://api.cohere.ai/v1/rerank"
    COHERE_RERANK_MODEL: str = "rerank-v3.5"
    LITELLM_RERANK_MODEL: str = "bge-reranker-large"
    RERANKER_FALLBACK_BASE_SCORE: float = 0.90
    RERANKER_FALLBACK_STEP: float = 0.08
    RERANKER_FALLBACK_MIN_SCORE: float = 0.45

    # =========================================================================
    # Search Timeouts
    # =========================================================================
    DENSE_EMBEDDING_TIMEOUT_SECONDS: float = 1.5
    QDRANT_SEARCH_TIMEOUT_SECONDS: float = 0.25

    # =========================================================================
    # Classifier (Intent Router)
    # =========================================================================
    CLASSIFIER_COMPLEX_QUERY_WORD_THRESHOLD: int = 35
    CLASSIFIER_CHITCHAT_RESPONSE: str = (
        "Hello! I am TitanRAG, your enterprise AI knowledge assistant. "
        "Ask me anything about your uploaded documents or workspace knowledge base."
    )
    CLASSIFIER_META_RESPONSE: str = (
        "I am TitanRAG. I index your documents using hybrid dense-sparse search "
        "and cited grounded generation. You can query policies, contracts, "
        "technical specifications, and tabular reports with verifiable citations."
    )

    # =========================================================================
    # Fusion
    # =========================================================================
    FUSION_STALENESS_PENALTY: float = 0.70

    # =========================================================================
    # Stripe Billing
    # =========================================================================
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_ENTERPRISE_PRICE_ID: str = ""
    STRIPE_CU_METER_EVENT_NAME: str = "compute_units_consumed"

    # =========================================================================
    # Sandbox
    # =========================================================================
    SANDBOX_SESSION_TTL_HOURS: int = 24
    SANDBOX_MAX_QUERIES_PER_HOUR: int = 10
    SANDBOX_MAX_UPLOADS_PER_DAY: int = 5
    SANDBOX_MAX_STORAGE_BYTES: int = 50 * 1024 * 1024  # 50MB
    SANDBOX_MAX_SESSIONS_PER_IP_PER_DAY: int = 5
    SANDBOX_EMAIL_DOMAIN: str = "sandbox.titanrag.io"

    # =========================================================================
    # Brand / White-Label
    # =========================================================================
    BRAND_DEFAULT_COMPANY_NAME: str = "TitanRAG"
    BRAND_DEFAULT_PRIMARY_COLOR: str = "#6366f1"
    BRAND_DEFAULT_ACCENT_COLOR: str = "#8b5cf6"
    BRAND_CACHE_TTL_SECONDS: int = 300
    BRAND_ASSET_MAX_BYTES: int = 2 * 1024 * 1024  # 2MB
    BRAND_PRESIGNED_URL_TTL_HOURS: int = 1

    # =========================================================================
    # OpenTelemetry
    # =========================================================================
    OTEL_ENABLED: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "titan-backend"
    OTEL_TRACES_SAMPLER: str = "always_on"

    # =========================================================================
    # Production Hardening & Security
    # =========================================================================
    STRICT_EMBEDDING_MODE: bool = False
    FAIL_ON_STORAGE_ERROR: bool = False
    CLAMAV_HOST: str | None = None
    CLAMAV_PORT: int = 3310
    ONNX_CLASSIFIER_PATH: str | None = Field(
        default_factory=lambda: (
            os.getenv("ONNX_CLASSIFIER_PATH")
            or (
                "/app/models/fast_path_classifier.onnx"
                if os.path.exists("/app/models/fast_path_classifier.onnx")
                else None
            )
            or ("models/fast_path_classifier.onnx" if os.path.exists("models/fast_path_classifier.onnx") else None)
            or (
                "packages/backend/models/fast_path_classifier.onnx"
                if os.path.exists("packages/backend/models/fast_path_classifier.onnx")
                else None
            )
        )
    )

    # =========================================================================
    # Compression
    # =========================================================================
    COMPRESSION_MINIMUM_SIZE: int = 1024

    # =========================================================================
    # CORS
    # =========================================================================
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000", "http://localhost:3001"])

    # =========================================================================
    # Computed Properties & Validators
    # =========================================================================

    @model_validator(mode="after")
    def _resolve_secrets(self) -> "Settings":
        """Auto-generate secrets in development; fail-fast in production."""
        is_production = self.ENVIRONMENT.lower() not in ("development", "dev", "test", "testing", "ci")

        # --- SECRET_KEY ---
        if self.SECRET_KEY == _DEV_SECRET_SENTINEL:
            if is_production:
                raise ValueError(
                    "CRITICAL: SECRET_KEY must be explicitly set in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
            self.SECRET_KEY = _generate_dev_secret("SECRET_KEY")

        # --- SCIM_BEARER_TOKEN ---
        if self.SCIM_BEARER_TOKEN == _DEV_SECRET_SENTINEL:
            if is_production:
                raise ValueError("CRITICAL: SCIM_BEARER_TOKEN must be explicitly set in production.")
            self.SCIM_BEARER_TOKEN = _generate_dev_secret("SCIM_BEARER_TOKEN")

        # --- LITELLM_MASTER_KEY ---
        if self.LITELLM_MASTER_KEY == _DEV_SECRET_SENTINEL:
            if is_production:
                raise ValueError("CRITICAL: LITELLM_MASTER_KEY must be explicitly set in production.")
            self.LITELLM_MASTER_KEY = _generate_dev_secret("LITELLM_MASTER_KEY")

        # --- Postgres password warning ---
        if is_production and self.POSTGRES_PASSWORD == "postgres_dev_password":
            raise ValueError(
                "CRITICAL: POSTGRES_PASSWORD is still the default dev password. Set a strong password for production."
            )

        # --- MinIO password warning ---
        if is_production and self.MINIO_ROOT_PASSWORD == "minioadmin":
            raise ValueError(
                "CRITICAL: MINIO_ROOT_PASSWORD is still the default. Set a strong password for production."
            )

        return self

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def get_sync_database_url(self) -> str:
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def get_cu_costs(self) -> dict[str, int]:
        """Return the CU cost table as a dictionary for runtime use."""
        return {
            "text_query": self.CU_COST_TEXT_QUERY,
            "ocr_page": self.CU_COST_OCR_PAGE,
            "batched_context_window": self.CU_COST_BATCHED_CONTEXT,
            "colpali_page": self.CU_COST_COLPALI_PAGE,
        }


settings = Settings()
