"""Site functions: calculations backend-ot runs for a site (energy, POI power, a BESS's round-trip
efficiency...). The AI sees only the ones backend-ot labels for it and the site admin approved;
the gated connector enforces that, and site_profile/functions.py bounds the result."""

from pydantic import AwareDatetime, Field

from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.knowledge.prompt_links import related_prompts
from intelli_gateway.schemas.context import RequestContext
from intelli_gateway.schemas.site_data import ParameterValue, SiteFunctionRun
from intelli_gateway.schemas.tools import JSONValue, ToolInput
from intelli_gateway.site_profile.functions import run_function
from intelli_gateway.tools.base import ToolDefinition, ToolError, tool
from intelli_gateway.tools.common import SiteToolLimits, dump, site_id_of
from intelli_gateway.utils.exceptions import InvalidRequestError, NotFoundError


class NoInput(ToolInput):
    pass


class RunSiteFunctionInput(ToolInput):
    name: str = Field(description="Function name as returned by list_site_functions.")
    start: AwareDatetime = Field(description="Start of the window, ISO 8601 with a UTC offset.")
    end: AwareDatetime = Field(description="End of the window, ISO 8601 with a UTC offset.")
    device_id: int | None = Field(
        default=None,
        description="Device functions only: the device to run it for (see list_site_functions).",
    )
    parameters: dict[str, ParameterValue] = Field(
        default_factory=dict[str, ParameterValue],
        description="Extra parameters the function declares (e.g. lookback_days); omit them "
        "for their defaults.",
    )


def build_site_function_tools(
    site_data: SiteDataConnector, knowledge: KnowledgeStore, limits: SiteToolLimits
) -> list[ToolDefinition]:
    @tool(
        name="list_site_functions",
        description="""
Lists the site's calculations (site functions) you can run with run_site_function: name,
summary, whether the result is one value set ("scalar") or a time series ("series"), extra
parameters, and for device functions the devices each applies to. Prefer a site function over
computing the same figure yourself from point history: its numbers match the dashboards.
""",
        input_model=NoInput,
    )
    async def list_site_functions(args: NoInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        devices = await site_data.list_devices(site_id)
        scripts = await knowledge.list_site_scripts(site_id)
        functions: list[JSONValue] = []
        for function in await site_data.list_site_functions(site_id):
            row = dump(function)
            if function.kind == "device":
                row["devices"] = [
                    {"device_id": device.device_id, "name": device.name, "type": device.type}
                    for device in devices
                    if not function.device_types or device.type in function.device_types
                ]
            prompts = related_prompts(scripts, function=function.name)
            if prompts:
                row["related_prompts"] = list[JSONValue](prompts)
            functions.append(row)
        return {"functions": functions}

    @tool(
        name="run_site_function",
        description=f"""
Runs one site function (from list_site_functions) over a time window and returns its result.
Series in the result are summarized: count, min, max, avg, first, last and a few samples. The
window may be at most {limits.history_max_days} days. Device functions need a device_id.
""",
        input_model=RunSiteFunctionInput,
    )
    async def run_site_function(args: RunSiteFunctionInput, ctx: RequestContext) -> JSONValue:
        site_id = site_id_of(ctx)
        run = SiteFunctionRun(
            name=args.name,
            start=args.start,
            end=args.end,
            device_id=args.device_id,
            parameters=args.parameters,
        )
        try:
            result = await run_function(
                site_data, site_id, run, limits.history_max_days, limits.history_samples
            )
        except NotFoundError as error:
            raise ToolError(
                str(error), hint="call list_site_functions for valid names and devices"
            ) from error
        except InvalidRequestError as error:
            raise ToolError(str(error)) from error
        output: dict[str, JSONValue] = {
            "function": args.name,
            "start": args.start.isoformat(),
            "end": args.end.isoformat(),
            **result,
        }
        prompts = related_prompts(await knowledge.list_site_scripts(site_id), function=args.name)
        if prompts:
            output["related_prompts"] = list[JSONValue](prompts)
        return output

    return [list_site_functions, run_site_function]
