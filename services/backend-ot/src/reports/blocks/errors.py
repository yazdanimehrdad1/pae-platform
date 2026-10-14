"""Turning a resolver's exception into the message stored in the report."""

from logger import get_logger
from utils.exceptions import AppError

logger = get_logger(__name__)


def block_error_message(error: Exception, what: str) -> str:
    """An application error keeps its message (e.g. 'no active_power point'); anything else is
    logged and stored as a generic message, so internals never end up in a report."""
    if isinstance(error, AppError):
        return error.message
    logger.error(f"Report: {what} failed: {error}", exc_info=error)
    return f"Could not generate {what}"
