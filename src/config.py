from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application specific settings
    APP_NAME: str = "VPN Top Servers"
    DEBUG: bool = False

    # Xray settings
    XRAY_API_URL: str = "127.0.0.1:8080"
    XRAY_START_INBOUND_PORT: int = 60000
    XRAY_MAX_CONCURRENT_SERVERS: int = 50

    # Subscription settings
    SUBSCRIPTION_TIMEOUT: int = 5  # Timeout for fetching subscription URLs
    SUBSCRIPTION_MAX_CONCURRENT_CONNECTIONS: int = (
        50  # Max concurrent connections for probing servers within a subscription
    )
    SUBSCRIPTION_ONLY_443_PORT: bool = False

    # HTTP Prober settings
    HTTP_PROBER_TIMEOUT: int = 10
    HTTP_PROBER_MAX_CONCURRENT_REQUESTS: int = (
        50  # Max concurrent requests for a single server check
    )

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: Path = Path("logs/app.log")

    # Pydantic model configuration
    model_config = SettingsConfigDict(
        env_file=".env",  # Load .env file if present
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra fields from environment variables
    )


# Create a single instance of settings to be used throughout the application
settings = Settings()
