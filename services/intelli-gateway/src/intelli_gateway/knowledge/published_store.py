"""PublishedKnowledgeStore: the KnowledgeStore the AI reads at runtime. It serves a site's latest
published knowledge, through the approved site profile:

- point guides are stored by (device_id, point name within the device); the tools use qualified
  names (`DEVICE.point`, with the approved device name), so names are translated here
- guides, documents and facts about devices no longer in the approved profile are set aside
  (kept in the knowledge, never served)
- a site that isn't onboarded has no knowledge
"""

from collections.abc import Sequence

from intelli_gateway.knowledge.search import search_notes
from intelli_gateway.knowledge.service import SiteKnowledgeService
from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    KnowledgeDocument,
    KnowledgeKind,
    PointGuide,
    SiteKnowledge,
    SitePrompt,
)
from intelli_gateway.site_profile.service import SiteProfileService


class PublishedKnowledgeStore:
    def __init__(self, knowledge: SiteKnowledgeService, profiles: SiteProfileService) -> None:
        self._knowledge = knowledge
        self._profiles = profiles

    async def _site(self, site_id: int) -> tuple[SiteKnowledge, dict[int, str]]:
        """The published knowledge and the approved devices (id -> name)."""
        view = await self._profiles.approved_view(site_id)
        version = await self._knowledge.published(site_id)
        if view is None or version is None:
            return SiteKnowledge(), {}
        return version.content, {device.device_id: device.name for device in view.catalog.devices}

    async def list_documents(self, site_id: int) -> list[KnowledgeDocument]:
        content, devices = await self._site(site_id)
        return [d for d in content.documents if d.device_id is None or d.device_id in devices]

    async def get_device_script(self, site_id: int, device_id: int) -> KnowledgeDocument | None:
        return next(
            (
                document
                for document in await self.list_documents(site_id)
                if document.kind is KnowledgeKind.IM_SCRIPT and document.device_id == device_id
            ),
            None,
        )

    async def search_notes(
        self, site_id: int, keywords: Sequence[str], limit: int, device_id: int | None = None
    ) -> list[KnowledgeDocument]:
        return search_notes(await self.list_documents(site_id), keywords, limit, device_id)

    async def get_point_guide(
        self, site_id: int, device_id: int, point_name: str
    ) -> PointGuide | None:
        return next(
            (
                guide
                for guide in await self.list_point_guides(site_id)
                if guide.device_id == device_id and guide.point_name == point_name
            ),
            None,
        )

    async def list_point_guides(self, site_id: int) -> list[PointGuide]:
        """Guides of approved devices, named as the tools name points (`DEVICE.point`)."""
        content, devices = await self._site(site_id)
        return [
            guide.model_copy(
                update={"point_name": f"{devices[guide.device_id]}.{guide.point_name}"}
            )
            for guide in content.point_guides
            if guide.device_id in devices
        ]

    async def list_device_facts(self, site_id: int) -> list[DeviceFacts]:
        content, devices = await self._site(site_id)
        return [facts for facts in content.device_facts if facts.device_id in devices]

    async def list_site_prompts(self, site_id: int) -> list[SitePrompt]:
        content, _devices = await self._site(site_id)
        return list(content.site_prompts)
