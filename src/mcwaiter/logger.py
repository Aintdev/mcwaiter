import logging
import logging.config
import sys

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[90m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[1;91m",
    }

    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, "")
        return f"{color}{super().format(record)}{self.RESET}"


DEFAULT_LOGGING = {
    "version": 1,
    "formatters": {
        "colored": {
            "()": ColoredFormatter,
            "format": "%(asctime)s %(levelname)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored",
            "level": "DEBUG",
            "stream": sys.stdout,
        }
    },
    "loggers": {
        __name__: {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
    },
}

logging.config.dictConfig(DEFAULT_LOGGING)
logger = logging.getLogger(__name__)