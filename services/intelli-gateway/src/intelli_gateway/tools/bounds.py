"""Keep tool outputs small enough for Claude's context."""

import json

from intelli_gateway.schemas.tools import JSONValue


def serialized_size(content: JSONValue) -> int:
    return len(json.dumps(content, ensure_ascii=False, default=str))


def bound_output(content: JSONValue, max_chars: int) -> JSONValue:
    """Return content unchanged if it fits; otherwise a truncated text preview of it."""
    text = json.dumps(content, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return content
    return {
        "truncated": True,
        "original_chars": len(text),
        "preview": text[:max_chars],
        "hint": "output was too large; narrow the request (filter, shorter time range)",
    }


def truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... [truncated, {len(text) - max_chars} more characters]"
