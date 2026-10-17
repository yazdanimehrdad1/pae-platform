"""OpenTelemetry hook. v1 is a no-op; wire a real tracer here without touching call sites."""

from collections.abc import Generator
from contextlib import contextmanager


@contextmanager
def span(name: str, **attributes: object) -> Generator[None]:
    """A tracing span around a unit of work (Claude call, tool call). No-op in v1."""
    del name, attributes
    yield
