from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application specific settings
    APP_NAME: str = "VPN Top Servers"
    DEBUG: bool = True
    PREFFER_PORTS: set = {443}

    # Xray settings
    XRAY_API_URL: str = "127.0.0.1:8080"
    XRAY_START_INBOUND_PORT: int = 60000
    XRAY_POOL_SIZE: int = 50
    XRAY_DIR: Path = Path(__file__).resolve().parent.parent / "xray"
    # Subscription settings
    SUBSCRIPTION_TIMEOUT: int = 5  # Timeout for fetching subscription URLs
    SUBSCRIPTION_MAX_CONCURRENT_CONNECTIONS: int = 50
    SUBSCRIPTION_ONLY_443_PORT: bool = False

    # Connection Prober settings
    CONNECTION_PROBER_TIMEOUT: int = 10
    CONNECTION_PROBER_MAX_CONCURRENT_CONNECTIONS: int = 100

    # HTTP Prober settings
    HTTP_PROBER_TIMEOUT: int = 15
    HTTP_PROBER_MAX_CONCURRENT_REQUESTS: int = 100
    HTTP_204_URLS: tuple[str, str, str] = (
        "https://www.google.com/generate_204",
        "https://www.cloudflare.com/cdn-cgi/trace",
        "https://httpbin.org/status/204",
    )
    DONT_ALIVE_CONNECTION_TIME: float = 999.0

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
