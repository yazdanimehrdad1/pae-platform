"""InMemoryKnowledgeAuthoringStore: knowledge drafts and versions in process memory, for tests.
Same behavior as the Postgres store (both pass tests/knowledge_authoring_store_contract.py)."""

from intelli_gateway.schemas.knowledge import KnowledgeDraft, KnowledgeVersion
from intelli_gateway.utils.exceptions import ConflictError

DRAFT_CHANGED = "the draft was changed by someone else since; reload it and try again"


class InMemoryKnowledgeAuthoringStore:
    def __init__(self) -> None:
        self._drafts: dict[int, KnowledgeDraft] = {}
        self._versions: dict[int, dict[int, KnowledgeVersion]] = {}

    async def get_draft(self, site_id: int) -> KnowledgeDraft | None:
        return self._drafts.get(site_id)

    async def save_draft(self, draft: KnowledgeDraft) -> None:
        stored = self._drafts.get(draft.site_id)
        if (stored.revision if stored else 0) + 1 != draft.revision:
            raise ConflictError(DRAFT_CHANGED)
        self._drafts[draft.site_id] = draft

    async def delete_draft(self, site_id: int) -> None:
        self._drafts.pop(site_id, None)

    async def get_version(
        self, site_id: int, version: int | None = None
    ) -> KnowledgeVersion | None:
        versions = self._versions.get(site_id, {})
        if not versions:
            return None
        return versions.get(max(versions) if version is None else version)

    async def list_versions(self, site_id: int) -> list[KnowledgeVersion]:
        versions = self._versions.get(site_id, {})
        return [versions[number] for number in sorted(versions, reverse=True)]

    async def publish(self, version: KnowledgeVersion, draft_revision: int | None) -> None:
        if draft_revision is not None:
            stored = self._drafts.get(version.site_id)
            if stored is None or stored.revision != draft_revision:
                raise ConflictError(DRAFT_CHANGED)
        versions = self._versions.setdefault(version.site_id, {})
        if version.version in versions:
            raise ConflictError(
                f"site {version.site_id} already has knowledge version {version.version}"
            )
        versions[version.version] = version
        self._drafts.pop(version.site_id, None)
