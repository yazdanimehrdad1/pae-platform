"""The tool-use loop with a scripted LLM client (no real API calls)."""

import asyncio
from collections.abc import Mapping

from fakes import ScriptedLLMClient, make_ctx, response, text, tool_use

from intelli_gateway.agent.loop import AgentLoop, append_user_text, close_dangling_tool_uses
from intelli_gateway.schemas.agent import ChatMessage, ContentBlock, LLMUsage, SystemBlock
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.tools import ToolResult, ToolSpec
from intelli_gateway.tools.local_provider import LocalToolProvider

SYSTEM = [SystemBlock("instructions"), SystemBlock("site knowledge", cache=True)]


def make_loop(
    llm: ScriptedLLMClient,
    provider: LocalToolProvider,
    max_iterations: int = 10,
    timeout_s: float = 5.0,
) -> AgentLoop:
    return AgentLoop(llm, provider, max_iterations=max_iterations, timeout_s=timeout_s)


class TestToolRoundTrip:
    async def test_runs_requested_tool_and_returns_final_answer(
        self, provider: LocalToolProvider
    ) -> None:
        llm = ScriptedLLMClient(
            response(
                text("Checking."),
                tool_use("t1", "get_point_values", {"point_names": ["POI.Frequency"]}),
                stop_reason="tool_use",
            ),
            response(text("Frequency is 50.0 Hz.")),
        )
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "Frequency?")

        assert result.answer == "Frequency is 50.0 Hz."
        assert result.stop_reason == "end_turn"
        assert result.iterations == 2
        assert [call.name for call in result.tool_calls] == ["get_point_values"]
        assert not result.tool_calls[0].is_error
        # The second request carries the tool result, linked by tool_use_id.
        tool_turn = llm.requests[1].messages[-1]
        assert tool_turn["role"] == "user"
        assert tool_turn["content"][0]["type"] == "tool_result"
        assert tool_turn["content"][0]["tool_use_id"] == "t1"

    async def test_sends_tools_and_system_blocks_every_iteration(
        self, provider: LocalToolProvider
    ) -> None:
        llm = ScriptedLLMClient(
            response(tool_use("t1", "list_points", {}), stop_reason="tool_use"),
            response(text("done")),
        )
        await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "q")
        for request in llm.requests:
            assert request.system == SYSTEM
            assert [spec.name for spec in request.tools] == sorted(
                spec.name for spec in request.tools
            )

    async def test_parallel_tool_calls_return_in_one_user_turn(
        self, provider: LocalToolProvider
    ) -> None:
        llm = ScriptedLLMClient(
            response(
                tool_use("a", "explain_point", {"point_name": "INV1.CabinetTemp"}),
                tool_use("b", "explain_point", {"point_name": "INV2.CabinetTemp"}),
                stop_reason="tool_use",
            ),
            response(text("INV2 runs hotter.")),
        )
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "Compare temps")
        tool_turn = llm.requests[1].messages[-1]
        assert [block["tool_use_id"] for block in tool_turn["content"]] == ["a", "b"]
        assert len(result.tool_calls) == 2

    async def test_tool_errors_go_back_to_claude_as_error_results(
        self, provider: LocalToolProvider
    ) -> None:
        llm = ScriptedLLMClient(
            response(
                tool_use("t1", "explain_point", {"point_name": "NOPE"}), stop_reason="tool_use"
            ),
            response(text("That point does not exist.")),
        )
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "q")
        assert result.tool_calls[0].is_error
        assert llm.requests[1].messages[-1]["content"][0]["is_error"] is True

    async def test_usage_is_summed_across_iterations(self, provider: LocalToolProvider) -> None:
        usage = LLMUsage(
            input_tokens=10,
            output_tokens=2,
            cache_read_input_tokens=5,
            cache_creation_input_tokens=1,
        )
        llm = ScriptedLLMClient(
            response(tool_use("t1", "list_points", {}), stop_reason="tool_use", usage=usage),
            response(text("done"), usage=usage),
        )
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "q")
        assert result.usage == usage + usage


class TestStopping:
    async def test_stops_at_max_iterations_with_a_valid_history(
        self, provider: LocalToolProvider
    ) -> None:
        llm = ScriptedLLMClient(
            *(
                response(tool_use(f"t{index}", "list_points", {}), stop_reason="tool_use")
                for index in range(3)
            )
        )
        result = await make_loop(llm, provider, max_iterations=3).run(make_ctx(), SYSTEM, [], "q")
        assert result.stop_reason == "max_iterations"
        assert result.iterations == 3
        assert "3 steps" in result.answer
        assert result.messages[-1]["role"] == "user"  # last tool results are in the history

    async def test_total_timeout(self, provider: LocalToolProvider) -> None:
        llm = ScriptedLLMClient(response(text("late")), delay_s=1.0)
        result = await make_loop(llm, provider, timeout_s=0.05).run(make_ctx(), SYSTEM, [], "q")
        assert result.stop_reason == "timeout"
        assert result.messages[-1]["role"] == "user"

    async def test_refusal(self, provider: LocalToolProvider) -> None:
        llm = ScriptedLLMClient(response(stop_reason="refusal", refusal_category="cyber"))
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "q")
        assert result.stop_reason == "refusal"
        assert result.refusal_category == "cyber"
        assert result.answer
        # An empty assistant turn is never appended.
        assert all(message["content"] for message in result.messages)

    async def test_pause_turn_continues(self, provider: LocalToolProvider) -> None:
        llm = ScriptedLLMClient(
            response(text("working"), stop_reason="pause_turn"), response(text("done"))
        )
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "q")
        assert result.answer == "done"
        assert result.iterations == 2


class TestHistory:
    async def test_history_is_append_only_and_not_modified_in_place(
        self, provider: LocalToolProvider
    ) -> None:
        thinking: ContentBlock = {"type": "thinking", "thinking": "", "signature": "sig"}
        history: list[ChatMessage] = [
            {"role": "user", "content": [text("first question")]},
            {"role": "assistant", "content": [thinking, text("first answer")]},
        ]
        snapshot = [dict(message) for message in history]
        llm = ScriptedLLMClient(response(text("second answer")))
        result = await make_loop(llm, provider).run(make_ctx(), SYSTEM, history, "second question")

        assert history == snapshot
        assert result.messages[:2] == history  # earlier turns unchanged, thinking block kept
        assert result.messages[2] == {"role": "user", "content": [text("second question")]}
        assert result.messages[3]["content"] == [text("second answer")]

    async def test_assistant_content_is_appended_exactly_as_returned(
        self, provider: LocalToolProvider
    ) -> None:
        blocks = [
            {"type": "thinking", "thinking": "", "signature": "abc"},
            tool_use("t1", "list_points", {}),
        ]
        llm = ScriptedLLMClient(response(*blocks, stop_reason="tool_use"), response(text("done")))
        await make_loop(llm, provider).run(make_ctx(), SYSTEM, [], "q")
        assert llm.requests[1].messages[1] == {"role": "assistant", "content": blocks}

    def test_user_text_extends_a_trailing_user_turn(self) -> None:
        messages: list[ChatMessage] = [
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t", "content": "x"}],
            }
        ]
        original = messages[0]
        append_user_text(messages, "next")
        assert len(messages) == 1
        assert [block["type"] for block in messages[0]["content"]] == ["tool_result", "text"]
        assert len(original["content"]) == 1  # the old dict was replaced, not mutated

    def test_dangling_tool_uses_get_error_results(self) -> None:
        messages: list[ChatMessage] = [
            {"role": "user", "content": [text("q")]},
            {"role": "assistant", "content": [tool_use("t1", "list_points", {})]},
        ]
        close_dangling_tool_uses(messages)
        assert messages[-1]["content"][0]["tool_use_id"] == "t1"
        assert messages[-1]["content"][0]["is_error"] is True


class SlowProvider:
    """Wraps a real provider; each call takes a while and records how many overlap."""

    def __init__(self, inner: LocalToolProvider) -> None:
        self._inner = inner
        self.running = 0
        self.peak = 0

    async def list_tools(self) -> list[ToolSpec]:
        return await self._inner.list_tools()

    async def call_tool(
        self, name: str, args: Mapping[str, object], ctx: RequestContext
    ) -> ToolResult:
        self.running += 1
        self.peak = max(self.peak, self.running)
        await asyncio.sleep(0.05)
        self.running -= 1
        return await self._inner.call_tool(name, args, ctx)


async def test_tools_in_one_turn_run_concurrently(provider: LocalToolProvider) -> None:
    slow = SlowProvider(provider)
    llm = ScriptedLLMClient(
        response(
            tool_use("a", "list_points", {}),
            tool_use("b", "list_points", {}),
            stop_reason="tool_use",
        ),
        response(text("done")),
    )
    await AgentLoop(llm, slow, max_iterations=5, timeout_s=5).run(make_ctx(), SYSTEM, [], "q")
    assert slow.peak == 2
