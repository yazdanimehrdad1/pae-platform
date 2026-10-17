"""Authorization for tool calls. Every tool call goes through `check` before reading any data.

v1: the site scope is enforced (a request is about one site, and the user must have access to
it). Role checks are a stub that allows everything.
"""

from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.tools.base import ToolError


def check(ctx: RequestContext, tool_name: str) -> None:
    """Raise ToolError if this context may not call this tool."""
    if ctx.site_id is None:
        raise ToolError("no site in request context", hint="tools only run inside a site request")
    if not ctx.can_access_site(ctx.site_id):
        raise ToolError("access to this site is not allowed")
    # TODO(auth): per-role tool permissions (e.g. viewer vs engineer). v1 allows every role.
    del tool_name
