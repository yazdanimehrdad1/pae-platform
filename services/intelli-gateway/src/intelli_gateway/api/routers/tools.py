"""The tool specs Claude sees (mirrors MCP list_tools; for debugging)."""

from fastapi import APIRouter, Depends

from intelli_gateway.agent.service import GatewayService
from intelli_gateway.api.dependencies import get_service
from intelli_gateway.schemas.api_models.responses import ToolSpecResponse

router = APIRouter(prefix="/v1", tags=["v1"])


@router.get(
    "/tools",
    response_model=list[ToolSpecResponse],
    summary="Tool specs Claude can call (mirrors MCP list_tools; for debugging)",
)
async def list_tools(service: GatewayService = Depends(get_service)) -> list[ToolSpecResponse]:
    return [
        ToolSpecResponse(
            name=spec.name, description=spec.description, input_schema=spec.input_schema
        )
        for spec in await service.list_tools()
    ]
