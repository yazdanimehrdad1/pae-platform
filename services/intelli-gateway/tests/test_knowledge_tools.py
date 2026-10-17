"""Knowledge tools: point guides, fault lookups, IM scripts, experience notes."""

from typing import cast

from fakes import Row, as_dict, make_ctx

from intelli_gateway.tools.local_provider import LocalToolProvider


class TestExplainPoint:
    async def test_guide_current_value_and_what_applies_now(
        self, provider: LocalToolProvider
    ) -> None:
        result = await provider.call_tool(
            "explain_point", {"point_name": "INV2.CabinetTemp"}, make_ctx()
        )
        content = as_dict(result.content)
        guide = as_dict(content["guide"])
        assert "cabinet" in cast(str, guide["meaning"])
        assert len(cast(list[object], guide["limits"])) == 2
        applies = cast(list[Row], content["applies_now"])
        assert [entry["message"] for entry in applies] == [
            "Derating: INV2 limits output to about 1500 kW"
        ]

    async def test_states_are_listed_briefly(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "explain_point", {"point_name": "INV2.Status"}, make_ctx()
        )
        states = cast(list[Row], as_dict(as_dict(result.content)["guide"])["states"])
        assert {state["label"] for state in states} >= {"RUNNING", "DERATED", "FAULT"}
        assert all("probable_causes" not in state for state in states)

    async def test_point_without_guide(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "explain_point", {"point_name": "POI.Frequency"}, make_ctx()
        )
        content = as_dict(result.content)
        assert content["guide"] is None
        assert "No engineer guide" in cast(str, content["note"])

    async def test_unknown_point(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("explain_point", {"point_name": "NOPE"}, make_ctx())
        assert result.is_error


class TestLookupFault:
    async def test_by_fault_code(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "lookup_fault", {"point_name": "INV2.FaultCode", "code": 101}, make_ctx()
        )
        content = as_dict(result.content)
        assert content["label"] == "CABINET_OVER_TEMP_TRIP"
        assert content["severity"] == "fault"
        assert content["checks"]
        assert content["safety_note"]

    async def test_by_bit_label(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "lookup_fault", {"point_name": "INV2.AlarmWord", "label": "over_temp"}, make_ctx()
        )
        content = as_dict(result.content)
        assert content["kind"] == "bit"
        assert content["code"] == 4

    async def test_unknown_code_lists_the_known_ones(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "lookup_fault", {"point_name": "INV2.FaultCode", "code": 999}, make_ctx()
        )
        assert result.is_error
        assert "101=CABINET_OVER_TEMP_TRIP" in cast(str, as_dict(result.content)["hint"])

    async def test_point_without_guide(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "lookup_fault", {"point_name": "POI.Frequency", "code": 1}, make_ctx()
        )
        assert result.is_error

    async def test_needs_code_or_label(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "lookup_fault", {"point_name": "INV2.FaultCode"}, make_ctx()
        )
        assert result.is_error
        assert as_dict(result.content)["error"] == "invalid arguments"


class TestGetDeviceScript:
    async def test_returns_the_script(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_device_script", {"device_id": 11}, make_ctx())
        assert "INV2.AlarmWord" in cast(str, as_dict(result.content)["script"])

    async def test_device_without_script(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool("get_device_script", {"device_id": 30}, make_ctx())
        assert result.is_error


class TestSearchExperienceNotes:
    async def test_best_match_first(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "search_experience_notes", {"keywords": ["INV2", "derate"]}, make_ctx()
        )
        notes = cast(list[Row], as_dict(result.content)["notes"])
        assert notes[0]["title"] == "INV2 derating on warm days"

    async def test_device_filter(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "search_experience_notes",
            {"keywords": ["communication", "network", "offline"], "device_id": 40},
            make_ctx(),
        )
        notes = cast(list[Row], as_dict(result.content)["notes"])
        assert [note["title"] for note in notes] == ["WS1 drops off the network"]

    async def test_notes_of_other_sites_are_not_searched(self, provider: LocalToolProvider) -> None:
        result = await provider.call_tool(
            "search_experience_notes", {"keywords": ["yaw"]}, make_ctx(site_id=1)
        )
        assert as_dict(result.content)["matches"] == 0
