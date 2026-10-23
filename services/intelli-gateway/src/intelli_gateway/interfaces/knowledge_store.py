"""Engineer-written knowledge store. Implementations: in memory (fake_data), Postgres next."""

from collections.abc import Sequence
from typing import Protocol

from intelli_gateway.schemas.knowledge import KnowledgeDocument, PointGuide


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
