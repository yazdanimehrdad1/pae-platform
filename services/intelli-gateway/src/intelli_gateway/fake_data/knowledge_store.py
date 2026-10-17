"""In-memory knowledge store over the fictional sites' documents and point guides."""

from collections.abc import Sequence

from intelli_gateway.fake_data.models import FakeSite
from intelli_gateway.fake_data.sites import FAKE_SITES
from intelli_gateway.schemas.knowledge import KnowledgeDocument, KnowledgeKind, PointGuide


class InMemoryKnowledgeStore:
    def __init__(
        self, documents: Sequence[KnowledgeDocument], guides: Sequence[PointGuide] = ()
    ) -> None:
        self._documents = list(documents)
        self._guides = list(guides)

    @classmethod
    def from_fake_sites(cls, sites: Sequence[FakeSite] = FAKE_SITES) -> "InMemoryKnowledgeStore":
        return cls(
            [document for fake in sites for document in fake.documents],
            [guide for fake in sites for guide in fake.guides],
        )

    async def list_documents(self, site_id: int) -> list[KnowledgeDocument]:
        return [document for document in self._documents if document.site_id == site_id]

    async def get_device_script(self, site_id: int, device_id: int) -> KnowledgeDocument | None:
        return next(
            (
                document
                for document in self._documents
                if document.site_id == site_id
                and document.kind is KnowledgeKind.IM_SCRIPT
                and document.device_id == device_id
            ),
            None,
        )

    async def search_notes(
        self, site_id: int, keywords: Sequence[str], limit: int, device_id: int | None = None
    ) -> list[KnowledgeDocument]:
        terms = [keyword.lower() for keyword in keywords if keyword.strip()]
        scored: list[tuple[int, KnowledgeDocument]] = []
        for document in self._documents:
            if document.site_id != site_id or document.kind is not KnowledgeKind.EXPERIENCE_NOTE:
                continue
            if device_id is not None and document.device_id != device_id:
                continue
            haystack = "\n".join([document.title, document.body, *document.point_names]).lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, document))
        scored.sort(key=lambda pair: (-pair[0], pair[1].title))
        return [document for _, document in scored[:limit]]

    async def get_point_guide(
        self, site_id: int, device_id: int, point_name: str
    ) -> PointGuide | None:
        return next(
            (
                guide
                for guide in self._guides
                if guide.site_id == site_id
                and guide.device_id == device_id
                and guide.point_name == point_name
            ),
            None,
        )

    async def list_point_guides(self, site_id: int) -> list[PointGuide]:
        return [guide for guide in self._guides if guide.site_id == site_id]
