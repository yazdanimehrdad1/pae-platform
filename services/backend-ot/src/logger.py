"""
Logging configuration.

Plain stdlib console logging to stdout, so container runtimes collect it.
"""

import logging
import sys


def setup_logging(log_level: str = "INFO") -> None:
    """
    Initialize logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)

