"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "DocReviewer – BPCR Reviewer"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    SAMPLES_DIR: Path = DATA_DIR / "samples"
    EXPORTS_DIR: Path = DATA_DIR / "exports"

    # OCR
    OCR_LANG: str = "en"
    OCR_USE_GPU: bool = False          # Set True if CUDA available
    OCR_CONFIDENCE_THRESHOLD: float = 0.5

    # Excel limits (practical warnings)
    EXCEL_MAX_ROWS_WARNING: int = 50000
    EXCEL_MAX_ROWS_HARD: int = 100000

    # ALCOA++
    ALCOA_STRICT_MODE: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
settings.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
