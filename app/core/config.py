"""
Application configuration using Pydantic Settings.
All settings are loaded from environment variables or .env file.
"""

from typing import List, Literal, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with type validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "FastCMS"
    APP_VERSION: str = "0.1.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    BASE_URL: str = "http://localhost:8000"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 1 day (24 hours * 60 minutes)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # 30 days

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | List[str]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # Admin
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: Optional[str] = None  # Only needed for initial admin creation

    # File Storage
    STORAGE_TYPE: Literal["local", "s3", "azure"] = "local"
    MAX_FILE_SIZE: int = 10485760  # 10MB in bytes
    ALLOWED_FILE_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/pdf",
        "application/zip",
        "text/plain",
        "text/csv",
    ]

    @field_validator("ALLOWED_FILE_TYPES", mode="before")
    @classmethod
    def parse_allowed_file_types(cls, v: str | List[str]) -> List[str]:
        """Parse allowed file types from string or list."""
        if isinstance(v, str):
            return [ft.strip() for ft in v.split(",")]
        return v

    # Local Storage (default)
    LOCAL_STORAGE_PATH: str = "./data/files"

    # AWS S3 Storage (optional - requires: pip install boto3 aioboto3)
    AWS_S3_BUCKET_NAME: str = ""
    AWS_S3_REGION: str = "us-east-1"
    AWS_S3_ENDPOINT_URL: str = ""  # For S3-compatible services (MinIO, DigitalOcean Spaces)
    AWS_S3_PUBLIC_URL: str = ""  # Custom public URL base
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Azure Blob Storage (optional - requires: pip install azure-storage-blob)
    AZURE_STORAGE_CONTAINER_NAME: str = ""
    AZURE_STORAGE_CONNECTION_STRING: str = ""  # Recommended method
    AZURE_STORAGE_ACCOUNT_NAME: str = ""  # Alternative method
    AZURE_STORAGE_ACCOUNT_KEY: str = ""  # Alternative method
    AZURE_STORAGE_PUBLIC_URL: str = ""  # Custom public URL base

    # Image Processing
    IMAGE_THUMBNAIL_SIZES: List[int] = [100, 300, 600]  # Thumbnail widths in pixels
    IMAGE_MAX_WIDTH: int = 2000  # Max image width for resizing
    IMAGE_MAX_HEIGHT: int = 2000  # Max image height for resizing
    IMAGE_QUALITY: int = 85  # JPEG quality (1-100)

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@fastcms.dev"
    SMTP_FROM_NAME: str = "FastCMS"
    # Security notifications — sent to user on security-relevant events
    SECURITY_NOTIFICATIONS_ENABLED: bool = True   # master switch (requires SMTP)
    SECURITY_LOGIN_NOTIFICATIONS: bool = False     # optional: email on every login

    # OAuth2 (optional)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_SECRET: str = ""

    # Redis for Caching, Rate Limiting, and Real-time Pub/Sub
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True

    # Account Lockout
    ACCOUNT_LOCKOUT_ENABLED: bool = True
    ACCOUNT_LOCKOUT_ATTEMPTS: int = 5       # Failed attempts before lockout
    ACCOUNT_LOCKOUT_DURATION: int = 1800    # Lockout duration in seconds (30 min)

    # IP Allowlist/Blocklist
    IP_FILTER_ENABLED: bool = False  # Set to True to enable IP filtering middleware

    # Password Policy
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    PASSWORD_HISTORY_COUNT: int = 0         # 0 = disabled

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 100
    RATE_LIMIT_PER_HOUR: int = 1000

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.ENVIRONMENT == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.ENVIRONMENT == "production"

    @property
    def database_is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return "sqlite" in self.DATABASE_URL.lower()

    @property
    def SMTP_ENABLED(self) -> bool:
        """Check if SMTP is configured."""
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)


# Create global settings instance
settings = Settings()
