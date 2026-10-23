"""Every local tool, built over the given site data and knowledge store."""

from intelli_gateway.interfaces.knowledge_store import KnowledgeStore
from intelli_gateway.interfaces.site_data import SiteDataConnector
from intelli_gateway.tools.alarm_tools import build_alarm_tools
from intelli_gateway.tools.base import ToolDefinition
from intelli_gateway.tools.common import SiteToolLimits
from intelli_gateway.tools.knowledge_tools import build_knowledge_tools
from intelli_gateway.tools.site_tools import build_site_tools


def build_local_tools(
    site_data: SiteDataConnector, knowledge: KnowledgeStore, limits: SiteToolLimits
) -> list[ToolDefinition]:
    return [
        *build_site_tools(site_data, knowledge, limits),
        *build_alarm_tools(site_data, limits),
        *build_knowledge_tools(site_data, knowledge, limits),
    ]
