"""The tool-use loop: send messages and tool specs; if Claude asks for tools, run them, append the
results, repeat; stop at a final answer, the iteration limit or the total timeout.

History is append-only: assistant turns are appended exactly as returned (thinking blocks
included), never edited, so prompt caching and thinking-block checks keep working.
"""

import asyncio
import json
import logging
import time
from collections.abc import Mapping

from intelli_gateway.interfaces.llm_client import LLMClient
from intelli_gateway.interfaces.tool_provider import ToolProvider
from intelli_gateway.schemas.agent import (
    AgentResult,
    ChatMessage,
    ContentBlock,
    LLMRequest,
    LLMUsage,
    SystemBlock,
    ToolCallRecord,
)
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import JSONValue
from intelli_gateway.utils.telemetry import span

logger = logging.getLogger(__name__)

SUMMARY_CHARS = 200
REFUSAL_ANSWER = "I can't help with that request."


def append_user_text(messages: list[ChatMessage], text: str) -> None:
    """Add the user's turn. If the history already ends with a user turn (tool results left
    by a stopped run), extend that turn instead of sending two user turns in a row."""
    block: ContentBlock = {"type": "text", "text": text}
    if messages and messages[-1]["role"] == "user":
        last = messages[-1]
        messages[-1] = {"role": "user", "content": [*last["content"], block]}
    else:
        messages.append({"role": "user", "content": [block]})


def close_dangling_tool_uses(messages: list[ChatMessage]) -> None:
    """If the last turn is an assistant turn with tool calls that never got results (timeout,
    iteration limit, max_tokens), add error results so the history stays valid."""
    if not messages or messages[-1]["role"] != "assistant":
        return
    pending = [block for block in messages[-1]["content"] if block.get("type") == "tool_use"]
    if pending:
        messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": block.get("id"),
                        "content": json.dumps({"error": "not run: the request stopped first"}),
                        "is_error": True,
                    }
                    for block in pending
                ],
            }
        )


def final_text(content: list[ContentBlock]) -> str:
    texts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n\n".join(text for text in texts if isinstance(text, str)).strip()


class AgentLoop:
    def __init__(
        self, llm: LLMClient, tools: ToolProvider, max_iterations: int, timeout_s: float
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._max_iterations = max_iterations
        self._timeout_s = timeout_s

    async def run(
        self,
        ctx: RequestContext,
        system: list[SystemBlock],
        history: list[ChatMessage],
        user_text: str,
    ) -> AgentResult:
        messages = list(history)  # the stored history is never modified in place
        append_user_text(messages, user_text)
        specs = await self._tools.list_tools()
        usage = LLMUsage()
        records: list[ToolCallRecord] = []
        iterations = 0
        answer = ""
        stop_reason = "unknown"
        model: str | None = None
        refusal_category: str | None = None
        try:
            async with asyncio.timeout(self._timeout_s):
                while True:
                    if iterations >= self._max_iterations:
                        stop_reason = "max_iterations"
                        answer = (
                            f"I stopped after {iterations} steps without a final answer. "
                            "Try a narrower question."
                        )
                        break
                    iterations += 1
                    with span("claude_call", iteration=iterations):
                        response = await self._llm.create(LLMRequest(system, specs, messages))
                    usage = usage + response.usage
                    model = response.model
                    self._log_call(
                        ctx, iterations, response.model, response.stop_reason, response.usage
                    )
                    if response.content:
                        messages.append({"role": "assistant", "content": response.content})
                    tool_uses = [b for b in response.content if b.get("type") == "tool_use"]
                    if response.stop_reason == "tool_use" and tool_uses:
                        # Parallel tool calls run concurrently; all results go back in one turn.
                        outcomes = await asyncio.gather(
                            *(self._run_tool(block, ctx) for block in tool_uses)
                        )
                        records.extend(record for record, _ in outcomes)
                        messages.append(
                            {"role": "user", "content": [result for _, result in outcomes]}
                        )
                        continue
                    if response.stop_reason == "pause_turn":
                        continue
                    stop_reason = response.stop_reason
                    answer = final_text(response.content)
                    if stop_reason == "refusal":
                        refusal_category = response.refusal_category
                        answer = answer or REFUSAL_ANSWER
                    break
        except TimeoutError:
            stop_reason = "timeout"
            answer = f"I ran out of time after {self._timeout_s:g} s. Try a narrower question."
        close_dangling_tool_uses(messages)
        logger.info(
            "agent_run",
            extra={
                "fields": {
                    "user_id": ctx.user_id,
                    "site_id": ctx.site_id,
                    "model": model,
                    "iterations": iterations,
                    "stop_reason": stop_reason,
                    "tool_calls": len(records),
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_read_input_tokens": usage.cache_read_input_tokens,
                    "cache_creation_input_tokens": usage.cache_creation_input_tokens,
                }
            },
        )
        return AgentResult(
            answer=answer,
            stop_reason=stop_reason,
            iterations=iterations,
            tool_calls=records,
            usage=usage,
            model=model,
            messages=messages,
            refusal_category=refusal_category,
        )

    async def _run_tool(
        self, block: ContentBlock, ctx: RequestContext
    ) -> tuple[ToolCallRecord, ContentBlock]:
        name = str(block.get("name", ""))
        raw_input = block.get("input")
        args: dict[str, JSONValue] = raw_input if isinstance(raw_input, dict) else {}
        started = time.perf_counter()
        result = await self._tools.call_tool(name, args, ctx)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        text = json.dumps(result.content, ensure_ascii=False, default=str)
        record = ToolCallRecord(
            name=name,
            args=args,
            summary=text[:SUMMARY_CHARS] + ("..." if len(text) > SUMMARY_CHARS else ""),
            duration_ms=duration_ms,
            is_error=result.is_error,
        )
        tool_result: ContentBlock = {
            "type": "tool_result",
            "tool_use_id": block.get("id"),
            "content": text,
            "is_error": result.is_error,
        }
        return record, tool_result

    @staticmethod
    def _log_call(
        ctx: RequestContext, iteration: int, model: str, stop_reason: str, usage: LLMUsage
    ) -> None:
        fields: Mapping[str, object] = {
            "user_id": ctx.user_id,
            "site_id": ctx.site_id,
            "model": model,
            "iteration": iteration,
            "stop_reason": stop_reason,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_input_tokens": usage.cache_read_input_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens,
        }
        logger.info("claude_call", extra={"fields": dict(fields)})
