"""Engineer-written knowledge the AI reads (published only). Implementations:
knowledge/published_store.py (the latest published version, through the approved site profile)
and tests/doubles/knowledge_store.py in tests."""

from collections.abc import Sequence
from typing import Protocol

from intelli_gateway.schemas.knowledge import (
    DeviceFacts,
    KnowledgeDocument,
    PointGuide,
    SiteScript,
)


class KnowledgeStore(Protocol):
    """Engineer-written knowledge: owned by this service."""

    async def list_documents(self, site_id: int) -> list[KnowledgeDocument]: ...

    async def get_device_script(self, site_id: int, device_id: int) -> KnowledgeDocument | None: ...

    async def search_notes(
        self, site_id: int, keywords: Sequence[str], limit: int, device_id: int | None = None
    ) -> list[KnowledgeDocument]:
        """Experience notes matching any keyword (title, text, linked point names), best match
        first. With device_id: only notes about that device."""
        ...

    async def get_point_guide(
        self, site_id: int, device_id: int, point_name: str
    ) -> PointGuide | None: ...

    async def list_point_guides(self, site_id: int) -> list[PointGuide]: ...

    async def list_device_facts(self, site_id: int) -> list[DeviceFacts]:
        """Admin-added ratings and notes of the site's devices."""
        ...

    async def list_site_scripts(self, site_id: int) -> list[SiteScript]:
        """The admin's general information about the site, in order."""
        ...
