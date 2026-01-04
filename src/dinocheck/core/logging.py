"""Logging configuration for Dinocheck."""

import logging
from pathlib import Path

LOGGER_NAME = "dinocheck"
DEFAULT_LOG_FILE = "dino.log"


def setup_logger(
    debug: bool = False,
    log_file: Path | None = None,
) -> logging.Logger:
    """Configure and return the Dinocheck logger.

    Args:
        debug: If True, enables DEBUG level logging to file.
        log_file: Path to log file. Defaults to dino.log in current directory.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Clear any existing handlers
    logger.handlers.clear()

    if debug:
        logger.setLevel(logging.DEBUG)

        # File handler for debug output
        file_path = log_file or Path(DEFAULT_LOG_FILE)
        file_handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        logger.setLevel(logging.WARNING)
        logger.addHandler(logging.NullHandler())

    return logger


def get_logger() -> logging.Logger:
    """Get the Dinocheck logger instance."""
    return logging.getLogger(LOGGER_NAME)
