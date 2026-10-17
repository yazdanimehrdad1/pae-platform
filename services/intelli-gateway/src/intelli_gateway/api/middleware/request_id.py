"""Request ids: taken from X-Request-Id or generated, put in the logging context and echoed."""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from intelli_gateway.utils.logger import request_id_var

REQUEST_ID_HEADER = "X-Request-Id"


async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
