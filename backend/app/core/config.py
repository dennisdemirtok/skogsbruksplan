from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    PROJECT_NAME: str = "SkogsplanSaaS"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = ""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://skogsplan:skogsplan@localhost:5432/skogsplan"

    # JWT Authentication
    SECRET_KEY: str = "change-this-to-a-real-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Skogsstyrelsen API
    SKOGSSTYRELSEN_API_BASE: str = "https://api.skogsstyrelsen.se/skogligagrunddata/v2"

    # Lantmateriet API — Fastighetsindelning Direkt (OGC API Features)
    LANTMATERIET_API_BASE: str = "https://api.lantmateriet.se/ogc-features/v1/fastighetsindelning"
    LANTMATERIET_API_KEY: str = ""
    LANTMATERIET_USER: str = ""
    LANTMATERIET_PASS: str = ""

    # SMHI Open Data API (free, no key required)
    SMHI_FORECAST_BASE: str = "https://opendata-download-metfcst.smhi.se/api/category/pmp3g/version/2"
    SMHI_WARNINGS_BASE: str = "https://opendata-download-warnings.smhi.se/ibww/api/version/1"

    # S3 / Object Storage
    S3_BUCKET: str = "skogsplan-uploads"
    S3_ENDPOINT: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "eu-north-1"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Raster data
    RASTER_DATA_PATH: str = "/data/rasters"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
