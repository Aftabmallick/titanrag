import os
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core System
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    QUICKSTART_MODE: bool = False
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "TitanRAG"
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "TitanRAG Enterprise Core"

    # Security & JWT
    SECRET_KEY: str = "titanrag-dev-secret-key-must-be-changed-in-production-min32chars!"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_PRIVATE_KEY: str | None = None
    JWT_PUBLIC_KEY: str | None = None

    # OAuth2 Providers
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GITHUB_CLIENT_ID: str | None = None
    GITHUB_CLIENT_SECRET: str | None = None

    # SCIM 2.0
    SCIM_BEARER_TOKEN: str = "titanrag-dev-scim-bearer-token-must-be-changed!"

    # Rate Limiting & FinOps Compute Units (CU)
    RATE_LIMIT_PER_MINUTE_ADMIN: int = 1000
    RATE_LIMIT_PER_MINUTE_MEMBER: int = 100
    RATE_LIMIT_PER_MINUTE_ANONYMOUS: int = 20
    DEFAULT_MONTHLY_CU_QUOTA: int = 10000

    # PostgreSQL
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_dev_password"
    POSTGRES_DB: str = "titanrag"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str | None = None
    SYNC_DATABASE_URL: str | None = None

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_BUCKET: str = "titanrag-documents"
    MINIO_USE_SSL: bool = False

    # LiteLLM & Models
    LITELLM_HOST: str = "localhost"
    LITELLM_PORT: int = 4000
    LITELLM_URL: str = "http://localhost:4000"
    LITELLM_MASTER_KEY: str = "sk-titanrag-litellm-master-key"
    DEFAULT_CHAT_MODEL: str = "deepseek-ai/deepseek-v4-flash-0731"
    DEFAULT_EMBEDDING_MODEL: str = "text-embedding-3-small"
    COHERE_API_KEY: str | None = None
    NVIDIA_API_KEY: str | None = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "deepseek-ai/deepseek-v4-flash-0731"
    RERANKER_TIMEOUT_MS: int = 400

    # OpenTelemetry
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_SERVICE_NAME: str = "titan-backend"
    OTEL_TRACES_SAMPLER: str = "always_on"

    # Production Hardening & Security
    STRICT_EMBEDDING_MODE: bool = False
    FAIL_ON_STORAGE_ERROR: bool = False
    CLAMAV_HOST: str | None = None
    CLAMAV_PORT: int = 3310
    ONNX_CLASSIFIER_PATH: str | None = Field(
        default_factory=lambda: (
            os.getenv("ONNX_CLASSIFIER_PATH")
            or ("/app/models/fast_path_classifier.onnx" if os.path.exists("/app/models/fast_path_classifier.onnx") else None)
            or ("models/fast_path_classifier.onnx" if os.path.exists("models/fast_path_classifier.onnx") else None)
            or ("packages/backend/models/fast_path_classifier.onnx" if os.path.exists("packages/backend/models/fast_path_classifier.onnx") else None)
        )
    )


    # CORS
    CORS_ORIGINS: list[str] = Field(default=["http://localhost:3000", "http://localhost:3001"])

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    def get_sync_database_url(self) -> str:
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


settings = Settings()
