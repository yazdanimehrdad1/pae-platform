"""FastAPI dependencies: the adapter context and adapter registry live on app.state."""

from fastapi import Request

from powerflow.interfaces.base import AdapterContext, AdapterRegistry


def get_context(request: Request) -> AdapterContext:
    return request.app.state.context


def get_adapters(request: Request) -> AdapterRegistry:
    return request.app.state.adapters
