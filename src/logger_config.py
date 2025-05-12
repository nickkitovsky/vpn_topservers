import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "%(asctime)s - %(levelname)s - %(message)s",
        },
        "file": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "console",
        },
        "file": {
            "class": "logging.FileHandler",
            # TODO: configure path for log file
            "filename": "../logs/app.log",
            "mode": "a",
            "encoding": "utf-8",
            "level": "INFO",
            "formatter": "file",
        },
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console", "file"],
    },
}


def setup_logging(*, debug: bool = False) -> None:
    if "handlers" in LOGGING_CONFIG and "console" in LOGGING_CONFIG["handlers"]:
        LOGGING_CONFIG["handlers"]["console"]["level"] = "DEBUG" if debug else "INFO"
    logging.config.dictConfig(LOGGING_CONFIG)
