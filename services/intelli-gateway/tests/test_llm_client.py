"""The parts of the Claude client that don't need the network."""

from fakes import text, tool_use

from intelli_gateway.schemas.agent import ContentBlock
from intelli_gateway.services.claude.client import echo_content

THINKING: ContentBlock = {"type": "thinking", "thinking": "", "signature": "s"}
FALLBACK: ContentBlock = {"type": "fallback", "from": {"model": "a"}, "to": {"model": "b"}}


class TestEchoContent:
    def test_without_fallback_content_is_unchanged(self) -> None:
        blocks = [THINKING, text("hi"), tool_use("t", "list_points", {})]
        assert echo_content(blocks) == blocks

    def test_pre_output_fallback_marker_is_dropped(self) -> None:
        assert echo_content([FALLBACK, THINKING, text("answer")]) == [THINKING, text("answer")]

    def test_mid_output_fallback_keeps_only_text_before_the_boundary(self) -> None:
        blocks = [
            THINKING,
            text("partial"),
            tool_use("t1", "list_points", {}),
            FALLBACK,
            THINKING,
            text("rest"),
        ]
        assert echo_content(blocks) == [text("partial"), THINKING, text("rest")]

    def test_last_fallback_marker_is_the_boundary(self) -> None:
        blocks = [text("a"), FALLBACK, THINKING, text("b"), FALLBACK, text("c")]
        assert echo_content(blocks) == [text("a"), text("b"), text("c")]
