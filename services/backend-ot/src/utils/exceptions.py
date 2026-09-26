"""
Custom application exceptions.

Provides a structured way to handle errors across the application layers.
"""

from typing import Any

from fastapi import status


class AppError(Exception):
    """Base class for all application errors."""
    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, message: str, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.payload = payload


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""
    http_status_code = status.HTTP_404_NOT_FOUND


class ConflictError(AppError):
    """Raised when an operation conflicts with existing data (e.g., duplicate unique field)."""
    http_status_code = status.HTTP_409_CONFLICT


class ValidationError(AppError):
    """Raised when input validation fails in the logic layer."""
    http_status_code = status.HTTP_400_BAD_REQUEST


class InternalError(AppError):
    """Raised for unexpected internal errors."""
    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR


class SiteProfileConfigError(AppError):
    """Raised when the site profile registry or a site's profile key is misconfigured."""
    http_status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
