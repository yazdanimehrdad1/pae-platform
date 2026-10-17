"""The HTTP API end to end, in process, with fake data and a scripted Claude."""

import httpx
from fakes import ScriptedLLMClient, fixed_clock, make_settings, response, text, tool_use

from intelli_gateway.app import create_app
from intelli_gateway.config import Settings
from intelli_gateway.schemas.agent import LLMRequest, LLMResponse
from intelli_gateway.schemas.api_models.responses import AskResponse, SiteResponse, ToolSpecResponse
from intelli_gateway.utils.exceptions import LLMUnavailableError
from intelli_gateway.wiring import build_services


def make_client(settings: Settings, llm: ScriptedLLMClient) -> httpx.AsyncClient:
    services = build_services(settings, llm=llm, clock=fixed_clock)
    app = create_app(settings, services)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


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
        # No EXTERNAL_API_URL in these settings: the forecast tool is not registered.
        assert names == [
            "explain_point",
            "get_active_alarms",
            "get_alarm_history",
            "get_device_script",
            "get_device_status",
            "get_point_history",
            "get_point_values",
            "get_site_overview",
            "list_points",
            "lookup_fault",
            "search_experience_notes",
        ]

    async def test_forecast_tool_registered_when_configured(self) -> None:
        settings = make_settings(EXTERNAL_API_URL="https://forecast.test/v1/forecast")
        async with make_client(settings, ScriptedLLMClient()) as client:
            response_ = await client.get("/api/v1/tools")
        assert "get_weather_forecast" in [spec["name"] for spec in response_.json()]


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

    async def test_prompt_layout_static_then_cached_site_block(self, settings: Settings) -> None:
        llm = ScriptedLLMClient(response(text("ok")))
        async with make_client(settings, llm) as client:
            await client.post("/api/v1/sites/1/ask", json={"question": "hi"})
        static, site_block = llm.requests[0].system
        assert not static.cache
        assert site_block.cache
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
                headers={"X-User-Id": "someone-else"},
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
