"""EmptyKnowledgeStore: the runtime knowledge store until engineer knowledge moves to this service's
Postgres (docs/KNOWLEDGE_PLAN.md, build step 2). It holds nothing: the agent says a point's
meaning is not documented rather than guess."""

from collections.abc import Sequence

from intelli_gateway.schemas.knowledge import KnowledgeDocument, PointGuide


class EmptyKnowledgeStore:
    async def list_documents(self, site_id: int) -> list[KnowledgeDocument]:
        del site_id
        return []

    async def get_device_script(self, site_id: int, device_id: int) -> KnowledgeDocument | None:
        del site_id, device_id
        return None

    async def search_notes(
        self, site_id: int, keywords: Sequence[str], limit: int, device_id: int | None = None
    ) -> list[KnowledgeDocument]:
        del site_id, keywords, limit, device_id
        return []

    async def get_point_guide(
        self, site_id: int, device_id: int, point_name: str
    ) -> PointGuide | None:
        del site_id, device_id, point_name
        return None

    async def list_point_guides(self, site_id: int) -> list[PointGuide]:
        del site_id
        return []
