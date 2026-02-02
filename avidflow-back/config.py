import secrets
import urllib.parse
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator, Field, AnyHttpUrl, ValidationInfo
from celery import Celery
from functools import lru_cache



BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # Base application settings
    APP_NAME: str = "Workflow Automation API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENV: str = "production"
    STATIC_URL: str = 'static/'
    STATIC_ROOT: Path = BASE_DIR / 'static'

    MEDIA_URL: str = 'media/'
    MEDIA_ROOT: Path = BASE_DIR / 'media'
    
    # API settings
    API_PREFIX: str = "/api"
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))

    KAVENEGAR_API_KEY: Optional[str] = None
    
    # CORS settings
    CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = ["*"]
    
    # Database settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_USER: str = "workflow"
    POSTGRES_PASSWORD: str = "workflow"
    POSTGRES_DB: str = "workflow_db"
    POSTGRES_PORT: str = "5432"
    DATABASE_URL: Optional[str] = None

    FRONTEND_URL: str = "http://localhost:3000"
    OAUTH_STATE_EXPIRE_SECONDS: int = 300
    TEST_WEBHOOK_STATE_EXPIRE_SECONDS: int = 120
    OAUTH2_CALLBACK_URL: Optional[str] = "http://localhost:8000/api/oauth2/callback"
    CHAT_BASE_URL: Optional[str] = "http://localhost:8000/chat"

    REDIS_URL: Optional[str] = None

    @field_validator("DATABASE_URL")
    def assemble_db_url(cls, v: Optional[str], info: ValidationInfo) -> str:
        """Generate database URL if not provided directly"""
        if v and isinstance(v, str):
            return v

        # Get the current settings values from the model
        # Use root data for context (whole model)
        values = info.data

        # Extract values with fallbacks
        username = values.get("POSTGRES_USER", "workflow")
        password = values.get("POSTGRES_PASSWORD", "workflow")
        host = values.get("POSTGRES_HOST", "localhost")
        port = values.get("POSTGRES_PORT", "5432")
        db_name = values.get("POSTGRES_DB", "workflow_db")

        return f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{db_name}"

    # Authentication settings
    JWT_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 360
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # RabbitMQ settings
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: str = "guest"
    RABBITMQ_VHOST: str = "/"
    
    # Celery settings
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # Set to True for testing
    CELERY_ACCEPT_CONTENT: List[str] = ["json"]
    CELERY_TASK_SERIALIZER: str = "json"
    CELERY_RESULT_SERIALIZER: str = "json"

    ADMIN_USER_MODEL: str = "AdminUser"
    ADMIN_USER_MODEL_USERNAME_FIELD: str = "username"
    ADMIN_SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    
    @field_validator("CELERY_BROKER_URL")
    def assemble_broker_url(cls, v: Optional[str], info: ValidationInfo) -> str:
        """Generate RabbitMQ broker URL if not provided directly"""
        if v and isinstance(v, str):
            return v

        # Access data via the data attribute of ValidationInfo
        data = info.data
        username = data.get("RABBITMQ_USER", "guest")
        password = data.get("RABBITMQ_PASSWORD", "guest")
        host = data.get("RABBITMQ_HOST", "localhost")
        port = data.get("RABBITMQ_PORT", 5672)
        vhost = data.get("RABBITMQ_VHOST", "/")

        # URL encode the vhost for AMQP URL
        encoded_vhost = urllib.parse.quote(vhost, safe="")

        return f"amqp://{username}:{password}@{host}:{port}/{encoded_vhost}"
    
    # Encryption settings
    ENCRYPTION_KEY: Optional[str] = None  # If not set, will be derived from SECRET_KEY
    
    # Worker settings
    WORKER_CONCURRENCY: int = 4
    
    # File storage
    UPLOAD_DIRECTORY: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Execution settings
    DEFAULT_EXECUTION_TIMEOUT: int = 30  # seconds
    MAX_WORKFLOW_SIZE: int = 10_000_000  # bytes
    
    # ZarinPal Payment Gateway
    ZARINPAL_SANDBOX: bool = False  # Set to False for production with your real merchant ID
    ZARINPAL_MERCHANT_ID: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ZARINPAL_CALLBACK_URL: str = "http://localhost:8000/api/payment/verify"
    ZARINPAL_FRONTEND_URL_REDIRECT: str = "http://localhost:3000/verify"

    # Langfuse Observability (optional - graceful degradation if not configured)
    # These values can be overridden via environment variables or .env file
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_BASE_URL: Optional[str] = None  # Cloud: None, Self-hosted: your URL

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance"""
    return Settings()


settings = get_settings()

