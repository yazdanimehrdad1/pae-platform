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


class UpstreamUnavailableError(GatewayError):
    """A system this service reads from failed or returned something unexpected. The API maps
    it to 503; inside a tool call it becomes an error result Claude can explain."""


class ExternalApiError(UpstreamUnavailableError):
    pass


class BackendOtError(UpstreamUnavailableError):
    pass
