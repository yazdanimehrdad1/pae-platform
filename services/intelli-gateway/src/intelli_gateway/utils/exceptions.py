"""Service errors. The API layer maps them to HTTP status codes; nothing here knows about HTTP."""


class GatewayError(Exception):
    """Base class for errors this service raises on purpose."""


class NotFoundError(GatewayError):
    pass


class ForbiddenError(GatewayError):
    pass


class LLMUnavailableError(GatewayError):
    """Claude could not be reached or rejected the request (auth, rate limit, outage)."""


class ConfigurationError(GatewayError):
    pass


class ExternalApiError(GatewayError):
    pass
