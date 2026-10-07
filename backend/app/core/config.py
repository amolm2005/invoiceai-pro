"""
Central application configuration.
All values are overridable via environment variables / .env file.
Never hardcode secrets here in production - this file only defines defaults for local dev.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # --- General ---
    APP_NAME: str = "InvoiceAI Pro"
    ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql://invoiceai:invoiceai_pass@db:5432/invoiceai"

    # --- Security / JWT ---
    JWT_SECRET_KEY: str = "CHANGE_THIS_SECRET_IN_PRODUCTION_ENV"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- CORS ---
    CORS_ORIGINS: List[str] = ["http://localhost:5173",
    "http://127.0.0.1:5173",]

    # --- File storage ---
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"
    ]

    # --- OCR ---
    OCR_ENGINE: str = "tesseract"  # "tesseract" or "easyocr"
    OCR_LANGUAGES: List[str] = ["en"]

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Risk thresholds (business rules) ---
    RISK_MEDIUM_DELAY_COUNT: int = 2
    RISK_HIGH_DELAY_COUNT: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
