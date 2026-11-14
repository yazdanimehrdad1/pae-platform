"""The HTTP API end to end, in process, with fake data and a scripted Claude."""

import httpx
from doubles.services import build_test_services
from fakes import ScriptedLLMClient, fixed_clock, make_settings, response, text, tool_use

from intelli_gateway.app import create_app
from intelli_gateway.config import Settings
from intelli_gateway.schemas.agent import LLMRequest, LLMResponse
from intelli_gateway.schemas.api_models.responses import (
    AskResponse,
    ConversationResponse,
    ConversationSummaryResponse,
    SiteResponse,
    ToolSpecResponse,
    TurnResponse,
)
from intelli_gateway.utils.exceptions import LLMUnavailableError

# Asking needs a real user (conversations are saved per user): in dev-header mode, a numeric id.
USER = {"X-User-Id": "1"}


def make_client(settings: Settings, llm: ScriptedLLMClient) -> httpx.AsyncClient:
    services = build_test_services(settings, llm=llm, clock=fixed_clock)
    app = create_app(settings, services)
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test", headers=USER
    )


class FailingLLMClient(ScriptedLLMClient):
    async def create(self, request: LLMRequest) -> LLMResponse:
        raise LLMUnavailableError("Claude is busy (529); retry later")


class TestReadEndpoints:
    async def test_healthz(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.get("/api/healthz")
        assert response_.json() == {"ok": True}
        assert response_.headers["X-Request-Id"]

    async def test_request_id_is_echoed(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.get("/api/healthz", headers={"X-Request-Id": "abc"})
        assert response_.headers["X-Request-Id"] == "abc"

    async def test_sites_are_filtered_by_access(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            every = await client.get("/api/v1/sites")
            limited = await client.get("/api/v1/sites", headers={"X-Site-Ids": "2"})
        assert [SiteResponse.model_validate(site).site_id for site in every.json()] == [1, 2]
        assert [site["site_id"] for site in limited.json()] == [2]

    async def test_bad_site_ids_header(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.get("/api/v1/sites", headers={"X-Site-Ids": "one"})
        assert response_.status_code == 400

    async def test_tools(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.get("/api/v1/tools")
        names = [ToolSpecResponse.model_validate(spec).name for spec in response_.json()]
        assert names == [
            "explain_point",
            "get_active_alarms",
            "get_alarm_history",
            "get_device_script",
            "get_device_status",
            "get_point_history",
            "get_point_values",
            "get_pv_forecast",
            "get_site_overview",
            "list_points",
            "list_site_functions",
            "lookup_fault",
            "run_site_function",
            "search_experience_notes",
        ]

    async def test_forecast_tool_not_registered_when_forecast_disabled(self) -> None:
        settings = make_settings(
            ANTHROPIC_API_KEY="test-key", FORECAST_ENABLED="false", AUTH_DEV_HEADERS="true"
        )
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.get("/api/v1/tools")
        names = [ToolSpecResponse.model_validate(spec).name for spec in response_.json()]
        assert "get_pv_forecast" not in names


class TestAsk:
    async def test_answer_tool_calls_and_usage(self, settings: Settings) -> None:
        llm = ScriptedLLMClient(
            response(
                tool_use("t1", "get_point_values", {"point_names": ["INV2.Status"]}),
                stop_reason="tool_use",
            ),
            response(text("INV2 is derated.")),
        )
        async with make_client(settings, llm) as client:
            response_ = await client.post("/api/v1/sites/1/ask", json={"question": "INV2 state?"})
        assert response_.status_code == 200
        body = AskResponse.model_validate(response_.json())
        assert body.answer == "INV2 is derated."
        assert body.stop_reason == "end_turn"
        assert body.iterations == 2
        assert body.tool_calls[0].name == "get_point_values"
        assert body.tool_calls[0].args == {"point_names": ["INV2.Status"]}
        assert body.usage.input_tokens == 200
        assert body.conversation_id
        assert body.turn_id
        assert body.created_at == fixed_clock()

    async def test_prompt_layout_static_then_cached_site_block(self, settings: Settings) -> None:
        llm = ScriptedLLMClient(response(text("ok")))
        async with make_client(settings, llm) as client:
            await client.post("/api/v1/sites/1/ask", json={"question": "hi"})
        static, site_block = llm.requests[0].system
        assert not static.cache
        assert site_block.cache
        # The answer format is part of the static (cache-stable) prompt.
        assert "At most 150 words" in static.text
        assert "Based on:" in static.text
        assert "Sunfield" in site_block.text
        assert "INV2 derating on warm days" in site_block.text
        # The current time goes in the user turn, never in the cached system prompt.
        assert "2026-06-15T12:00:00" not in static.text + site_block.text
        first_user_block = llm.requests[0].messages[0]["content"][0]
        assert "2026-06-15T12:00:00" in str(first_user_block["text"])

    async def test_conversation_continues(self, settings: Settings) -> None:
        llm = ScriptedLLMClient(response(text("first")), response(text("second")))
        async with make_client(settings, llm) as client:
            first = (await client.post("/api/v1/sites/1/ask", json={"question": "a"})).json()
            await client.post(
                "/api/v1/sites/1/ask",
                json={"question": "b", "conversation_id": first["conversation_id"]},
            )
        roles = [message["role"] for message in llm.requests[1].messages]
        assert roles == ["user", "assistant", "user"]

    async def test_conversation_of_another_user_is_not_found(self, settings: Settings) -> None:
        llm = ScriptedLLMClient(response(text("first")))
        async with make_client(settings, llm) as client:
            first = (await client.post("/api/v1/sites/1/ask", json={"question": "a"})).json()
            response_ = await client.post(
                "/api/v1/sites/1/ask",
                json={"question": "b", "conversation_id": first["conversation_id"]},
                headers={"X-User-Id": "2"},
            )
        assert response_.status_code == 404

    async def test_conversation_of_another_site_is_not_found(self, settings: Settings) -> None:
        llm = ScriptedLLMClient(response(text("first")))
        async with make_client(settings, llm) as client:
            first = (await client.post("/api/v1/sites/1/ask", json={"question": "a"})).json()
            response_ = await client.post(
                "/api/v1/sites/2/ask",
                json={"question": "b", "conversation_id": first["conversation_id"]},
            )
        assert response_.status_code == 404

    async def test_unknown_site(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.post("/api/v1/sites/99/ask", json={"question": "a"})
        assert response_.status_code == 404

    async def test_asking_needs_a_real_user(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            client.headers.pop("X-User-Id")
            response_ = await client.post("/api/v1/sites/1/ask", json={"question": "a"})
        assert response_.status_code == 401

    async def test_a_monitor_may_ask(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient(response(text("ok")))) as client:
            response_ = await client.post(
                "/api/v1/sites/1/ask", json={"question": "a"}, headers={"X-Roles": "monitor"}
            )
        assert response_.status_code == 200

    async def test_site_outside_users_access(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.post(
                "/api/v1/sites/1/ask", json={"question": "a"}, headers={"X-Site-Ids": "2"}
            )
        assert response_.status_code == 403

    async def test_empty_question_is_rejected(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.post("/api/v1/sites/1/ask", json={"question": ""})
        assert response_.status_code == 422

    async def test_claude_unavailable(self, settings: Settings) -> None:
        async with make_client(settings, FailingLLMClient()) as client:
            response_ = await client.post("/api/v1/sites/1/ask", json={"question": "a"})
        assert response_.status_code == 503
        assert "busy" in response_.json()["detail"]


class TestConversations:
    """Saved conversations: a user sees only their own, for sites they can access; every answer
    keeps what the AI read (tools and arguments), its tokens and the user's feedback."""

    async def ask_twice(self, client: httpx.AsyncClient) -> AskResponse:
        first = AskResponse.model_validate(
            (
                await client.post("/api/v1/sites/1/ask", json={"question": "  INV2   state?  "})
            ).json()
        )
        await client.post(
            "/api/v1/sites/1/ask",
            json={"question": "and INV1?", "conversation_id": first.conversation_id},
        )
        return first

    def llm(self) -> ScriptedLLMClient:
        return ScriptedLLMClient(
            response(
                tool_use("t1", "get_point_values", {"point_names": ["INV2.Status"]}),
                stop_reason="tool_use",
            ),
            response(text("INV2 is derated.")),
            response(text("INV1 is fine.")),
        )

    async def test_list_and_open_a_conversation(self, settings: Settings) -> None:
        async with make_client(settings, self.llm()) as client:
            first = await self.ask_twice(client)
            listed = (await client.get("/api/v1/conversations")).json()
            for_site_2 = (await client.get("/api/v1/conversations?site_id=2")).json()
            opened = await client.get(f"/api/v1/conversations/{first.conversation_id}")
        summaries = [ConversationSummaryResponse.model_validate(item) for item in listed]
        assert [(s.conversation_id, s.site_id, s.title, s.turns) for s in summaries] == [
            (first.conversation_id, 1, "INV2 state?", 2)
        ]
        assert for_site_2 == []
        assert opened.status_code == 200
        conversation = ConversationResponse.model_validate(opened.json())
        assert [turn.question for turn in conversation.turns] == ["  INV2   state?  ", "and INV1?"]
        assert [turn.answer for turn in conversation.turns] == ["INV2 is derated.", "INV1 is fine."]
        first_turn = conversation.turns[0]
        assert first_turn.turn_id == first.turn_id
        # What the AI read is kept (tools and arguments), with the tokens it used.
        assert [(call.name, call.args) for call in first_turn.tool_calls] == [
            ("get_point_values", {"point_names": ["INV2.Status"]})
        ]
        assert first_turn.usage.input_tokens == 200
        # The site's local time when asked (Europe/Berlin: UTC+2 in June).
        assert first_turn.site_local_time == "2026-06-15T14:00:00+02:00"
        assert first_turn.feedback is None

    async def test_feedback_on_an_answer(self, settings: Settings) -> None:
        async with make_client(settings, self.llm()) as client:
            first = await self.ask_twice(client)
            url = f"/api/v1/conversations/{first.conversation_id}/turns/{first.turn_id}/feedback"
            rated = await client.put(url, json={"rating": "down", "comment": "wrong inverter"})
            cleared = await client.put(url, json={"rating": None, "comment": "ignored"})
            missing = await client.put(
                f"/api/v1/conversations/{first.conversation_id}/turns/999/feedback",
                json={"rating": "up"},
            )
            bad = await client.put(url, json={"rating": "meh"})
        turn = TurnResponse.model_validate(rated.json())
        assert (turn.feedback, turn.feedback_comment, turn.feedback_at) == (
            "down",
            "wrong inverter",
            fixed_clock(),
        )
        cleared_turn = TurnResponse.model_validate(cleared.json())
        assert (cleared_turn.feedback, cleared_turn.feedback_comment) == (None, None)
        assert (missing.status_code, bad.status_code) == (404, 422)

    async def test_rename_a_conversation(self, settings: Settings) -> None:
        async with make_client(settings, self.llm()) as client:
            first = await self.ask_twice(client)
            url = f"/api/v1/conversations/{first.conversation_id}"
            renamed = await client.patch(url, json={"title": "  Inverter   2 derate "})
            blank = await client.patch(url, json={"title": "   "})
            listed = (await client.get("/api/v1/conversations")).json()
            missing = await client.patch("/api/v1/conversations/nope", json={"title": "x"})
        summary = ConversationSummaryResponse.model_validate(renamed.json())
        assert (summary.title, summary.turns) == ("Inverter 2 derate", 2)
        assert [item["title"] for item in listed] == ["Inverter 2 derate"]
        assert (blank.status_code, missing.status_code) == (422, 404)

    async def test_delete_a_conversation_for_good(self, settings: Settings) -> None:
        async with make_client(settings, self.llm()) as client:
            first = await self.ask_twice(client)
            url = f"/api/v1/conversations/{first.conversation_id}"
            deleted = await client.delete(url)
            opened = await client.get(url)
            listed = (await client.get("/api/v1/conversations")).json()
            again = await client.delete(url)
        assert (deleted.status_code, deleted.content) == (204, b"")
        assert (opened.status_code, listed, again.status_code) == (404, [], 404)

    async def test_another_users_conversation_is_not_found(self, settings: Settings) -> None:
        async with make_client(settings, self.llm()) as client:
            first = await self.ask_twice(client)
            other = {"X-User-Id": "2"}
            listed = (await client.get("/api/v1/conversations", headers=other)).json()
            opened = await client.get(
                f"/api/v1/conversations/{first.conversation_id}", headers=other
            )
            rated = await client.put(
                f"/api/v1/conversations/{first.conversation_id}/turns/{first.turn_id}/feedback",
                json={"rating": "up"},
                headers=other,
            )
            renamed = await client.patch(
                f"/api/v1/conversations/{first.conversation_id}",
                json={"title": "mine now"},
                headers=other,
            )
            deleted = await client.delete(
                f"/api/v1/conversations/{first.conversation_id}", headers=other
            )
            still_there = await client.get(f"/api/v1/conversations/{first.conversation_id}")
        assert listed == []
        assert (opened.status_code, rated.status_code) == (404, 404)
        assert (renamed.status_code, deleted.status_code) == (404, 404)
        assert ConversationResponse.model_validate(still_there.json()).title == "INV2 state?"

    async def test_conversations_of_sites_out_of_reach_are_hidden(self, settings: Settings) -> None:
        async with make_client(settings, self.llm()) as client:
            first = await self.ask_twice(client)
            only_site_2 = {"X-Site-Ids": "2"}
            listed = (await client.get("/api/v1/conversations", headers=only_site_2)).json()
            opened = await client.get(
                f"/api/v1/conversations/{first.conversation_id}", headers=only_site_2
            )
        assert listed == []
        assert opened.status_code == 404

    async def test_conversations_need_a_real_user(self, settings: Settings) -> None:
        async with make_client(settings, ScriptedLLMClient()) as client:
            client.headers.pop("X-User-Id")
            response_ = await client.get("/api/v1/conversations")
        assert response_.status_code == 401
